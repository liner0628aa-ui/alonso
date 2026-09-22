"""Hand-calculated geometry and missingness contracts; no external data needed."""
import math

import pyarrow as pa
import pytest

from src.spatial.coordinates import canonical_table, team_relative, PitchConfig
from src.spatial.features import frame_features, window_features


def observation(pid, team, x, y, **changes):
    return dict(match_id='m', period=1, timestamp_s=0., frame_id=0,
                team_id=team, player_id=pid, track_id=pid, x_m=x, y_m=y,
                visible=True, detected=True, source='synthetic',
                coordinate_confidence=None, identity_confidence=None,
                attacking_direction='positive_x' if team == 'A' else 'negative_x') | changes


def geometry():
    return [observation('A1', 'A', 50., 34.), observation('A2', 'A', 53., 38.),
            observation('A3', 'A', 40., 10.), observation('B1', 'B', 55., 34.),
            observation('B2', 'B', 70., 50.)]


def compute(rows, **kwargs):
    return frame_features(canonical_table(rows), **kwargs)


def test_exact_frame_geometry():
    players, teams, quality = compute(geometry(), min_team_players=2)
    p = {r['player_id']: r for r in players.to_pylist()}
    a = p['A1']
    assert a['nearest_teammate_distance_m'] == 5
    assert a['nearest_opponent_distance_m'] == 5
    assert [a[k] for k in ('local_teammates_r5', 'local_opponents_r5',
                          'local_teammates_r10', 'local_opponents_r10')] == [1, 1, 1, 1]
    assert p['A2']['nearest_opponent_distance_m'] == pytest.approx(math.sqrt(20))
    assert p['A3']['nearest_teammate_distance_m'] == 26
    assert p['A3']['local_teammates_r5'] == 0  # observed neighbours, none inside radius
    assert a['pitch_zone'] == 'central'
    assert p['A3']['pitch_zone'] == 'left_wide'
    assert p['B2']['pitch_zone'] == 'left_halfspace'  # y=68-50 in own attack frame
    assert p['B2']['team_x_m'] == 35
    t = {r['team_id']: r for r in teams.to_pylist()}
    assert (t['A']['team_width_m'], t['A']['team_depth_m']) == (28, 13)
    assert (t['B']['team_width_m'], t['B']['team_depth_m']) == (16, 15)
    assert t['A']['visible_team_players'] == 3
    assert quality.to_pylist()[0]['valid_player_observations'] == 5


def test_opposite_attack_invariant_includes_opponent_distances():
    rows = geometry()
    mirror = [r | dict(x_m=105-r['x_m'], y_m=68-r['y_m'],
                      attacking_direction='negative_x' if r['team_id'] == 'A' else 'positive_x') for r in rows]
    original = compute(rows, min_team_players=2)
    mirrored = compute(mirror, min_team_players=2)
    for a, b in zip(original[0].to_pylist(), mirrored[0].to_pylist()):
        for key in ('team_x_m', 'team_y_m', 'pitch_zone', 'nearest_teammate_distance_m',
                    'nearest_opponent_distance_m', 'local_opponents_r5'):
            assert a[key] == pytest.approx(b[key]) if isinstance(a[key], float) else a[key] == b[key]
    assert original[1].to_pylist() == mirrored[1].to_pylist()
    for p in ('positive_x', 'negative_x'):
        xy = team_relative(12., 7., p)
        assert xy == ((12., 7.) if p == 'positive_x' else (93., 61.))


@pytest.mark.parametrize('y,zone', [(0, 'left_wide'), (13.6, 'left_halfspace'),
    (27.2, 'central'), (40.8, 'right_halfspace'), (54.4, 'right_wide'), (68, 'right_wide')])
def test_exact_zone_boundaries(y, zone):
    p, _, _ = compute([observation('a', 'A', 50, y)])
    assert p.to_pylist()[0]['pitch_zone'] == zone


def test_missing_opponents_single_player_and_incomplete_visibility():
    rows = [observation('a', 'A', 10, 10), observation('b', 'B', 12, 10, visible=False),
            observation('c', 'A', None, None), observation('d', 'A', 15, 10, detected=False)]
    p, t, q = compute(rows)
    a = p.to_pylist()[0]
    assert a['nearest_opponent_distance_m'] is None
    assert a['local_opponents_r5'] is None
    assert a['nearest_teammate_distance_m'] is None
    assert a['local_teammates_r10'] is None
    assert all(r['pitch_zone'] is None for r in p.to_pylist()[1:])
    assert t.to_pylist()[0]['team_width_m'] is None
    assert t.to_pylist()[0]['visible_team_players'] == 1
    assert q.to_pylist()[0]['missing_coordinate_rows'] == 1


@pytest.mark.parametrize('changes', [dict(x_m=float('inf')), dict(x_m=float('nan')),
    dict(x_m=-.2), dict(y_m=68.2), dict(x_m=None), dict(timestamp_s='0'),
    dict(timestamp_s=True), dict(track_id=None), dict(period=1.5),
    dict(attacking_direction=None), dict(visible='yes')])
def test_invalid_observation_rejected(changes):
    with pytest.raises(ValueError):
        canonical_table([observation('a', 'A', 10, 10, **changes)])


def test_duplicates_and_inconsistent_frame_clock_rejected():
    row = geometry()[0]
    for other in (row, row | dict(track_id='another'), row | dict(player_id='b', track_id='b', timestamp_s=1)):
        with pytest.raises(ValueError):
            canonical_table([row, other])


def test_tolerance_is_flagged_not_clipped_or_counted():
    p, _, q = compute([observation('a', 'A', -.05, 20)])
    assert p.to_pylist()[0]['x_m'] == -.05
    assert p.to_pylist()[0]['pitch_zone'] is None
    assert q.to_pylist()[0]['out_of_pitch_rows'] == 1


def test_empty_tables_have_typed_schemas():
    rows = canonical_table([])
    assert rows.schema.field('x_m').type == pa.float64()
    p, t, q = frame_features(rows)
    assert p.num_rows == t.num_rows == q.num_rows == 0
    pw, tw = window_features(p, t, start_s=0, end_s=1, sample_interval_s=.1)
    assert pw.num_rows == tw.num_rows == 0
    assert 'tracking_halfspace_occupancy' in pw.column_names


def test_window_denominators_missing_frames_and_anonymous_tracks():
    rows = [observation('a', 'A', 50, 20), observation('b', 'A', 53, 24),
            observation('c', 'B', 55, 20),
            observation('a', 'A', 60, 34, timestamp_s=.2, frame_id=2),
            observation('b', 'A', None, None, timestamp_s=.2, frame_id=2),
            observation(None, 'B', 80, 50, track_id='anon', timestamp_s=.2, frame_id=2)]
    p, t, _ = compute(rows, min_team_players=2)
    pw, tw = window_features(p, t, start_s=0, end_s=.3, sample_interval_s=.1,
                            expected_frames={('m', 1, 'A', 'player:a'): 3})
    a = next(r for r in pw.to_pylist() if r['player_id'] == 'a')
    assert a['tracking_avg_x_m'] == 55
    assert a['tracking_avg_y_m'] == 27
    assert a['tracking_left_halfspace_occupancy'] == .5
    assert a['tracking_central_occupancy'] == .5
    assert a['tracking_halfspace_occupancy'] == .5
    assert a['observed_frames'] == 2
    assert a['expected_frames'] == 3
    assert a['visible_fraction'] == pytest.approx(2/3)
    assert a['time_span_s'] == .2
    assert a['valid_nearest_teammate_frames'] == 1
    assert a['mean_nearest_teammate_distance_m'] == a['median_nearest_teammate_distance_m'] == 5
    assert a['valid_nearest_opponent_frames'] == 2
    b = next(r for r in pw.to_pylist() if r['player_id'] == 'b')
    assert b['observed_frames'] == 1 and b['visible_fraction'] is None
    assert any(r['entity_id'] == 'track:anon' for r in pw.to_pylist())
    team = next(r for r in tw.to_pylist() if r['team_id'] == 'A')
    assert team['mean_team_width_m'] == team['median_team_width_m'] == 4
    assert team['mean_team_depth_m'] == team['median_team_depth_m'] == 3
    assert team['valid_team_frames'] == 1
    assert team['observed_frames'] == 2 and team['expected_frames'] == 3
    assert team['mean_visible_team_players'] == 1.5


def test_all_invalid_window_stays_null():
    p, t, _ = compute([observation('a', 'A', None, None)])
    pw, tw = window_features(p, t, start_s=0, end_s=1, sample_interval_s=.1)
    row = pw.to_pylist()[0]
    assert row['observed_frames'] == 0
    assert row['tracking_avg_x_m'] is None and row['tracking_halfspace_occupancy'] is None
    assert row['time_span_s'] is None
    assert tw.to_pylist()[0]['valid_team_frames'] == 0


def test_irregular_sampling_and_bad_denominators_rejected():
    p, t, _ = compute([observation('a', 'A', 10, 10, timestamp_s=.15)])
    with pytest.raises(ValueError, match='grid'):
        window_features(p, t, start_s=0, end_s=1, sample_interval_s=.1)
    p, t, _ = compute(geometry())
    with pytest.raises(ValueError, match='expected'):
        window_features(p, t, start_s=0, end_s=1, sample_interval_s=.1,
                        expected_frames={('m', 1, 'A', 'player:A1'): 0})


def test_configurable_radii_and_zones():
    p, _, _ = compute(geometry(), radii=(3., 6.), pitch=PitchConfig(lane_fractions=(.1,.3,.7,.9)))
    a = p.to_pylist()[0]
    assert a['local_teammates_r3'] == 0 and a['local_teammates_r6'] == 1
    assert 'local_teammates_r5' not in a


def test_duplicate_grid_slots_cannot_inflate_coverage():
    p, t, _ = compute([observation('a', 'A', 10, 10),
                       observation('a', 'A', 10, 10, timestamp_s=1e-9, frame_id=1)])
    with pytest.raises(ValueError, match='grid slot'):
        window_features(p, t, start_s=0, end_s=.1, sample_interval_s=.1)


def test_radius_labels_cannot_collide():
    with pytest.raises(ValueError, match='radius labels'):
        compute(geometry(), radii=(5., 5.000001))


def test_team_frame_coverage_is_separate_from_visibility():
    p, t, _ = compute([observation('a', 'A', 10, 10, visible=False)])
    _, tw = window_features(p, t, start_s=0, end_s=.1, sample_interval_s=.1)
    row = tw.to_pylist()[0]
    assert row['frame_coverage_fraction'] == 1
    assert row['visible_fraction'] == 0
    assert row['visible_frames'] == 0
    assert row['valid_team_frames'] == 0
