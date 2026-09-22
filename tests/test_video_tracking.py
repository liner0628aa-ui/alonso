"""Adapter contracts with prescribed detections and the real third-party tracker."""
import numpy as np
import pytest

from src.video_tracking.detection import ground_point, person_detections
from src.video_tracking.tracking import SegmentTracker, track_summary
from src.video_tracking.team_assignment import validate_team_config, canonical_rows
from src.spatial.coordinates import canonical_table


def detection(x=20., confidence=.9):
    return dict(bbox=[x, 10., x+10., 30.], detector_confidence=confidence)


def teams():
    return dict(teams={'A': 'positive_x', 'B': 'negative_x'},
                team_assignments={'s:1': {'team_id': 'A', 'source_method': 'manual_review'}})


def source_row(**changes):
    return dict(frame_id=0, timestamp_s=0., track_id='s:1', pitch_x_raw=30., pitch_y_raw=20.,
                team_id='A', team_assignment_method='manual_review', excluded=False,
                homography_failure=False) | changes


def test_ground_point_and_person_filter_keep_raw_confidence():
    assert ground_point([10, 20, 30, 70]) == (20., 70.)
    prediction = dict(boxes=np.array([[10, 20, 30, 70], [1, 2, 3, 4], [5, 6, 7, 8]]),
                      labels=np.array([1, 37, 1]), scores=np.array([.84321, .99, .05]))
    found = person_detections(prediction, threshold=.1)
    assert len(found) == 1
    assert found[0]['detector_confidence'] == .84321
    assert found[0]['bbox'] == [10., 20., 30., 70.]


@pytest.mark.parametrize('box', [[2, 0, 1, 3], [0, 2, 3, 2], [0, 0, float('nan'), 4]])
def test_invalid_box_fails(box):
    with pytest.raises(ValueError):
        ground_point(box)


def test_real_bytetrack_stability_missing_frame_and_scope():
    tracker = SegmentTracker('s', fps=10.)
    a = tracker.update(0, 0., [detection()])
    b = tracker.update(1, .1, [detection(20.2)])
    missing = tracker.update(2, .2, [])
    c = tracker.update(3, .3, [detection(20.4)])
    assert a[0]['track_id'] == b[0]['track_id'] == c[0]['track_id'] == 's:1'
    assert missing == []
    other = SegmentTracker('other', fps=10.).update(0, 0., [detection()])
    assert other[0]['track_id'] != a[0]['track_id']
    summary = track_summary(a+b+c, fps=10.)[0]
    assert summary['observed_frames'] == 3
    assert summary['start_frame'] == 0 and summary['end_frame'] == 3
    assert summary['time_span_s'] == pytest.approx(.3)
    assert summary['observed_duration_s'] == pytest.approx(.3)
    assert summary['mean_detector_confidence'] == pytest.approx(.9)


def test_untracked_low_confidence_detection_is_preserved():
    rows = SegmentTracker('s', fps=10.).update(0, 0., [detection(confidence=.15)])
    assert len(rows) == 1 and rows[0]['track_id'] is None
    assert rows[0]['detector_confidence'] == .15


@pytest.mark.parametrize('frame,time', [(0, .1), (1, 0.), (2, .2), (1, .11)])
def test_duplicate_skipped_frames_and_irregular_clock_rejected(frame, time):
    tracker = SegmentTracker('s', fps=10.)
    tracker.update(0, 0., [])
    with pytest.raises(ValueError):
        tracker.update(frame, time, [])


def test_anonymous_canonical_rows_preserve_unknown_confidence():
    table = canonical_table(canonical_rows([source_row()], teams(), match_id='m', period=1))
    row = table.to_pylist()[0]
    assert row['player_id'] is None
    assert row['coordinate_confidence'] is row['identity_confidence'] is None
    assert row['x_m'] == 30. and row['attacking_direction'] == 'positive_x'


def test_unassigned_team_blocks_and_bad_coordinates_reach_authoritative_validator():
    with pytest.raises(ValueError, match='team'):
        canonical_rows([source_row(team_id=None, team_assignment_method=None)], teams(), match_id='m', period=1)
    rows = canonical_rows([source_row(pitch_x_raw=120.)], teams(), match_id='m', period=1)
    with pytest.raises(ValueError, match='outside pitch'):
        canonical_table(rows)


def test_untracked_is_not_invented_identity_and_excluded_nonplayer_is_explicit():
    assert canonical_rows([source_row(track_id=None)], teams(), match_id='m', period=1) == []
    assert canonical_rows([source_row(excluded=True)], teams(), match_id='m', period=1) == []


@pytest.mark.parametrize('change', [dict(teams={'A': 'unknown'}),
    dict(team_assignments={'s:1': {'team_id': 'C', 'source_method': 'manual_review'}}),
    dict(team_assignments={'s:1': {'team_id': 'A', 'source_method': 'prediction'}})])
def test_invalid_team_direction_or_method_rejected(change):
    with pytest.raises(ValueError):
        validate_team_config(teams() | change)
