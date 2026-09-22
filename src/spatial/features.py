"""Observed-subset features with explicit counts and regular-grid window means."""
from collections import defaultdict

import numpy as np
import pyarrow as pa

from .coordinates import (PitchConfig, TRACKING_SCHEMA, ZONES, canonical_table,
                          finite_number, in_pitch, team_relative)

FRAME_KEYS = ('match_id', 'period', 'frame_id', 'timestamp_s')
TEAM_KEYS = (*FRAME_KEYS, 'team_id')
DEFAULT_RADII = (5., 10.)


def typed_table(rows, fields):
    return pa.Table.from_pylist(rows, schema=pa.schema(fields))


def key_fields(names):
    return [(k, TRACKING_SCHEMA.field(k).type) for k in names]


def radius_names(radii):
    if not radii or any(not finite_number(r) or r <= 0 for r in radii) or len(set(radii)) != len(radii):
        raise ValueError('Unique positive finite radii required')
    if len({f'{r:g}' for r in radii}) != len(radii):
        raise ValueError('Configured radius labels collide at six significant digits')
    return [(f'local_{kind}_r{r:g}', kind, r) for r in radii for kind in ('teammates', 'opponents')]


def frame_features(table, *, pitch=None, radii=DEFAULT_RADII, min_team_players=3):
    """Return player frames (including invalid rows), team frames, frame quality.

    Distances use a shared physical frame, avoiding comparison of differently
    rotated opponents. NULL neighbour counts mean no observed support, whereas
    zero means observed support exists but lies outside the inclusive radius.
    """
    pitch = pitch or PitchConfig()
    if isinstance(min_team_players, bool) or not isinstance(min_team_players, int) or min_team_players < 2:
        raise ValueError('Team extents require an explicit threshold >=2')
    densities = radius_names(radii)
    rows = canonical_table(table, pitch=pitch).to_pylist()
    frames, teams_by_period = defaultdict(list), defaultdict(set)
    for row in rows:
        frames[tuple(row[k] for k in FRAME_KEYS)].append(row)
        teams_by_period[(row['match_id'], row['period'])].add(row['team_id'])
    players, teams, quality = [], [], []
    for frame, group in sorted(frames.items()):
        frame_info = dict(zip(FRAME_KEYS, frame))
        valid = [r for r in group if r['visible'] is True and r['detected'] is True and in_pitch(r, pitch)]
        xy = np.array([[r['x_m'], r['y_m']] for r in valid], dtype=float).reshape(-1, 2)
        distances = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=2)
        valid_index = {r['track_id']: i for i, r in enumerate(valid)}
        for row in group:
            result = row | dict(valid_observation=row['track_id'] in valid_index,
                                team_x_m=None, team_y_m=None, pitch_zone=None,
                                nearest_teammate_distance_m=None, nearest_opponent_distance_m=None,
                                **{name: None for name, _, _ in densities})
            if result['valid_observation']:
                x, y = team_relative(row['x_m'], row['y_m'], row['attacking_direction'], pitch)
                # Round boundary products to avoid 0.6*68 putting exact 40.8 in the wrong lane.
                boundaries = [round(f*pitch.width_m, 10) for f in pitch.lane_fractions]
                result.update(team_x_m=x, team_y_m=y, pitch_zone=ZONES[sum(y >= b for b in boundaries)])
                i = valid_index[row['track_id']]
                for kind, singular in (('teammates', 'teammate'), ('opponents', 'opponent')):
                    indices = [j for j, other in enumerate(valid) if j != i and
                               ((other['team_id'] == row['team_id']) == (kind == 'teammates'))]
                    if indices:
                        ds = distances[i, indices]
                        result[f'nearest_{singular}_distance_m'] = float(ds.min())
                        for name, category, radius in densities:
                            if category == kind:
                                result[name] = int(np.count_nonzero(ds <= radius + 1e-9))
            players.append(result)
        for team in sorted(teams_by_period[frame[:2]]):
            visible = [r for r in valid if r['team_id'] == team]
            enough = len(visible) >= min_team_players
            teams.append(frame_info | dict(team_id=team, visible_team_players=len(visible),
                team_width_m=float(np.ptp([r['y_m'] for r in visible])) if enough else None,
                team_depth_m=float(np.ptp([r['x_m'] for r in visible])) if enough else None,
                min_team_players=min_team_players))
        quality.append(frame_info | dict(input_rows=len(group), valid_player_observations=len(valid),
            missing_coordinate_rows=sum(r['x_m'] is None for r in group),
            out_of_pitch_rows=sum(r['x_m'] is not None and not in_pitch(r, pitch) for r in group),
            nonvisible_or_unknown_rows=sum(r['visible'] is not True for r in group),
            nondetected_or_unknown_rows=sum(r['detected'] is not True for r in group),
            visible_teams=len({r['team_id'] for r in valid})))
    player_fields = list(TRACKING_SCHEMA) + [pa.field('valid_observation', pa.bool_()),
        pa.field('team_x_m', pa.float64()), pa.field('team_y_m', pa.float64()), pa.field('pitch_zone', pa.string()),
        pa.field('nearest_teammate_distance_m', pa.float64()), pa.field('nearest_opponent_distance_m', pa.float64())]
    player_fields += [pa.field(name, pa.int64()) for name, _, _ in densities]
    team_fields = key_fields(TEAM_KEYS) + [('visible_team_players', pa.int64()),
        ('team_width_m', pa.float64()), ('team_depth_m', pa.float64()), ('min_team_players', pa.int64())]
    quality_fields = key_fields(FRAME_KEYS) + [(k, pa.int64()) for k in (
        'input_rows', 'valid_player_observations', 'missing_coordinate_rows', 'out_of_pitch_rows',
        'nonvisible_or_unknown_rows', 'nondetected_or_unknown_rows', 'visible_teams')]
    return typed_table(players, player_fields), typed_table(teams, team_fields), typed_table(quality, quality_fields)


def entity_id(row):
    return 'player:'+row['player_id'] if row['player_id'] is not None else 'track:'+row['track_id']


def _stat(rows, key, stat=np.mean):
    values = [r[key] for r in rows if r[key] is not None]
    return float(stat(values)) if values else None


def window_features(player_frames, team_frames, *, start_s, end_s, sample_interval_s,
                    expected_frames=None):
    """Aggregate [start_s,end_s) separately by match/period; regular grid only.

    Frame shares estimate tracking time under uniform sampling; never bridge gaps.
    expected_frames maps (match, period, team, entity_id) to known eligible counts.
    Counts are caller-supplied roster/time support, never inferred from detections.
    """
    if (not all(finite_number(v) for v in (start_s, end_s, sample_interval_s)) or
            start_s < 0 or end_s <= start_s or sample_interval_s <= 0):
        raise ValueError('Valid time window and positive sampling interval required')
    slots = (end_s-start_s)/sample_interval_s
    if not np.isclose(slots, round(slots), atol=1e-7, rtol=0):
        raise ValueError('Window must span an integer number of grid intervals')
    expected_window = round(slots)
    expected_frames = expected_frames or {}
    groups, team_groups = defaultdict(list), defaultdict(list)
    grid_frames = {}
    for table, target, is_player in ((player_frames, groups, True), (team_frames, team_groups, False)):
        for row in table.to_pylist():
            if not start_s <= row['timestamp_s'] < end_s:
                continue
            grid = (row['timestamp_s']-start_s)/sample_interval_s
            if not np.isclose(grid, round(grid), atol=1e-7, rtol=0):
                raise ValueError('Timestamp is off the declared regular grid')
            grid_key = (row['match_id'], row['period'], round(grid))
            if grid_frames.setdefault(grid_key, row['frame_id']) != row['frame_id']:
                raise ValueError('Multiple frames occupy the same grid slot')
            key = (row['match_id'], row['period'], row['team_id'])
            if is_player:
                key += (entity_id(row),)
            target[key].append(row)
    # Include explicitly eligible but completely absent targets, without inventing positions.
    for key, count in expected_frames.items():
        if (len(key) != 4 or not key[3].startswith(('player:', 'track:')) or
                isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= expected_window):
            raise ValueError('Invalid expected frame key/count')
        groups.setdefault(key, [])
    common = dict(window_start_s=start_s, window_end_s=end_s, sample_interval_s=sample_interval_s)
    players, teams = [], []
    density_columns = [k for k in player_frames.column_names if k.startswith('local_')]
    for key, rows in sorted(groups.items()):
        valid = [r for r in rows if r['valid_observation']]
        if len({r['frame_id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate entity frame in window')
        expected = expected_frames.get(key)
        if expected is not None and len(valid) > expected:
            raise ValueError('observed_frames exceeds expected frames')
        pid = key[3][7:] if key[3].startswith('player:') else None
        times = [r['timestamp_s'] for r in valid]
        result = dict(zip(('match_id', 'period', 'team_id', 'entity_id'), key)) | common | dict(
            player_id=pid, track_ids='|'.join(sorted({r['track_id'] for r in rows})),
            observed_frames=len(valid), input_rows=len(rows), expected_frames=expected,
            visible_fraction=len(valid)/expected if expected else None,
            time_span_s=max(times)-min(times) if times else None,
            tracking_avg_x_m=_stat(valid, 'team_x_m'), tracking_avg_y_m=_stat(valid, 'team_y_m'))
        for zone in ZONES:
            result[f'tracking_{zone}_occupancy'] = sum(r['pitch_zone'] == zone for r in valid)/len(valid) if valid else None
        result['tracking_halfspace_occupancy'] = (result['tracking_left_halfspace_occupancy'] +
            result['tracking_right_halfspace_occupancy']) if valid else None
        for kind in ('teammate', 'opponent'):
            column = f'nearest_{kind}_distance_m'
            result[f'valid_nearest_{kind}_frames'] = sum(r[column] is not None for r in valid)
            result['mean_'+column] = _stat(valid, column)
            result['median_'+column] = _stat(valid, column, np.median)
        for column in density_columns:
            result['mean_'+column] = _stat(valid, column)
            result['valid_'+column+'_frames'] = sum(r[column] is not None for r in valid)
        players.append(result)
    for key, rows in sorted(team_groups.items()):
        if len({r['frame_id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate team frame in window')
        result = dict(zip(('match_id', 'period', 'team_id'), key)) | common | dict(
            observed_frames=len(rows), expected_frames=expected_window,
            frame_coverage_fraction=len(rows)/expected_window,
            visible_frames=sum(r['visible_team_players'] > 0 for r in rows),
            visible_fraction=sum(r['visible_team_players'] > 0 for r in rows)/expected_window,
            mean_visible_team_players=_stat(rows, 'visible_team_players'),
            valid_team_frames=sum(r['team_width_m'] is not None and r['team_depth_m'] is not None for r in rows))
        for dim in ('width', 'depth'):
            column = f'team_{dim}_m'
            result['mean_'+column] = _stat(rows, column)
            result['median_'+column] = _stat(rows, column, np.median)
            result[f'valid_team_{dim}_frames'] = sum(r[column] is not None for r in rows)
        teams.append(result)
    base_fields = key_fields(('match_id', 'period', 'team_id')) + [(k, pa.float64()) for k in common]
    coverage_fields = [('observed_frames', pa.int64()), ('expected_frames', pa.int64()), ('visible_fraction', pa.float64())]
    player_fields = base_fields + [('entity_id', pa.string()), ('player_id', pa.string()), ('track_ids', pa.string()),
        ('input_rows', pa.int64()), *coverage_fields, ('time_span_s', pa.float64()),
        ('tracking_avg_x_m', pa.float64()), ('tracking_avg_y_m', pa.float64())]
    player_fields += [(f'tracking_{zone}_occupancy', pa.float64()) for zone in (*ZONES, 'halfspace')]
    for kind in ('teammate', 'opponent'):
        player_fields += [(f'valid_nearest_{kind}_frames', pa.int64())] + [
            (f'{agg}_nearest_{kind}_distance_m', pa.float64()) for agg in ('mean', 'median')]
    for column in density_columns:
        player_fields += [('mean_'+column, pa.float64()), ('valid_'+column+'_frames', pa.int64())]
    team_fields = base_fields + coverage_fields + [('frame_coverage_fraction', pa.float64()),
        ('visible_frames', pa.int64()), ('mean_visible_team_players', pa.float64()), ('valid_team_frames', pa.int64())]
    for dim in ('width', 'depth'):
        team_fields += [(f'{agg}_team_{dim}_m', pa.float64()) for agg in ('mean', 'median')]
        team_fields += [(f'valid_team_{dim}_frames', pa.int64())]
    return typed_table(players, player_fields), typed_table(teams, team_fields)
