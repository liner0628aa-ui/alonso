"""Report guards test scientific invariants, including deliberately bad results."""
import pyarrow as pa
import pytest

from src.analysis.spatial_engine_report import check_results, feature_dictionary
from src.spatial.coordinates import canonical_table
from src.spatial.features import frame_features, window_features


def results():
    rows = []
    for team, pid, x, y in [('A', 'a', 50, 34), ('A', 'b', 53, 38), ('B', 'c', 55, 34)]:
        rows.append(dict(match_id='m', period=1, timestamp_s=0., frame_id=0, team_id=team,
            player_id=pid, track_id=pid, x_m=x, y_m=y, visible=True, detected=True, source='test',
            coordinate_confidence=None, identity_confidence=None,
            attacking_direction='positive_x' if team == 'A' else 'negative_x'))
    p, t, q = frame_features(canonical_table(rows), min_team_players=2)
    pw, tw = window_features(p, t, start_s=0, end_s=.1, sample_interval_s=.1)
    return p, t, q, pw, tw


def test_sanity_and_dictionary_cover_all_exported_columns():
    p, t, q, pw, tw = results()
    assert check_results(p, t, pw, tw)['status'] == 'PASS'
    tables = dict(player_frame=p, team_frame=t, frame_quality=q, player_window=pw, team_window=tw)
    dictionary = feature_dictionary(tables, min_team_players=2)
    assert {(r['level'], r['feature']) for r in dictionary} == {
        (level, name) for level, table in tables.items() for name in table.column_names}
    assert all(r['definition'] and r['missing_policy'] and r['version'] == 'spatial-v1' for r in dictionary)


@pytest.mark.parametrize('table_index,column,value', [
    (0, 'nearest_opponent_distance_m', -1.), (1, 'team_width_m', 69.),
    (1, 'team_depth_m', 106.), (3, 'tracking_central_occupancy', .5),
    (3, 'tracking_avg_x_m', float('inf')), (4, 'visible_fraction', 1.1)])
def test_impossible_outputs_fail_loudly(table_index, column, value):
    tables = list(results())
    rows = tables[table_index].to_pylist()
    rows[0][column] = value
    tables[table_index] = pa.Table.from_pylist(rows, schema=tables[table_index].schema)
    p, t, _, pw, tw = tables
    with pytest.raises(ValueError):
        check_results(p, t, pw, tw)
