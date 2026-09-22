"""Provider mapping is separate from the football geometry tests."""
import pytest

from src.data.sources.skillcorner_tracking import adapt_frames, parse_timestamp


def metadata():
    return dict(id=42, pitch_length=104, pitch_width=68,
                home_team={'id': 1}, away_team={'id': 2},
                home_team_side=['right_to_left', 'left_to_right'],
                players=[dict(id=10, team_id=1, trackable_object=110),
                         dict(id=20, team_id=2, trackable_object=120)])


def frame():
    return dict(frame=10, timestamp='00:00:01.0', period=1,
                player_data=[dict(player_id=10, x=-26, y=17, is_detected=True),
                             dict(player_id=20, x=None, y=None, is_detected=False)])


def test_provider_centered_axes_dimensions_direction_and_missingness():
    rows = adapt_frames([frame()], metadata()).to_pylist()
    assert (rows[0]['x_m'], rows[0]['y_m']) == (26.25, 17)
    assert rows[0]['attacking_direction'] == 'negative_x'
    assert rows[0]['track_id'] == 'skillcorner:track:110'
    assert rows[0]['player_id'] == 'skillcorner:player:10'
    assert rows[0]['timestamp_s'] == 1
    assert rows[0]['coordinate_confidence'] is None
    assert rows[1]['x_m'] is None and rows[1]['y_m'] is None
    assert rows[1]['visible'] is False and rows[1]['detected'] is False
    assert rows[1]['attacking_direction'] == 'positive_x'
    second = frame() | dict(period=2)
    assert adapt_frames([second], metadata()).to_pylist()[0]['attacking_direction'] == 'positive_x'


@pytest.mark.parametrize('change', [dict(home_team_side=[]), dict(pitch_width=None),
    dict(home_team_side=['unknown', 'left_to_right']), dict(players=[])])
def test_provider_unknown_metadata_rejected(change):
    with pytest.raises(ValueError):
        adapt_frames([frame()], metadata() | change)


def test_unknown_detection_preserved_and_empty_prematch_skipped():
    f = frame()
    f['player_data'][0]['is_detected'] = None
    rows = adapt_frames([dict(frame=0, period=None, timestamp=None, player_data=[]), f], metadata())
    assert rows.num_rows == 2
    assert rows.to_pylist()[0]['visible'] is None
    assert rows.to_pylist()[0]['detected'] is None


def test_timestamp_is_numeric_match_clock_seconds_without_inventing_period_offset():
    assert parse_timestamp('00:45:00.1') == 2700.1
    for invalid in (None, 'no clock', '00:60:00', 1., True):
        with pytest.raises(ValueError):
            parse_timestamp(invalid)
