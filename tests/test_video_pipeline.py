"""Synthetic contracts; generated blank video is a decoder fixture, not real E2E."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pyarrow.parquet as pq
import pytest

from src.video_tracking.calibration import fit_calibration
from src.video_tracking.pipeline import (validate_config, build_source_rows, quality_summary,
    integrate_source, decode_segment, run_video, prepare_output, write_blocked_report, SOURCE_SCHEMA)
from src.video_tracking.tracking import SegmentTracker


def config():
    points = [[0., 0.], [105., 0.], [105., 68.], [0., 68.]]
    pixels = (np.asarray(points)*5 + [10, 10]).tolist()
    return dict(match_id='synthetic_contract', period=1, segment_id='synthetic',
        segment_start_frame=0, segment_end_frame=3, period_time_at_segment_start_s=0.,
        rights=dict(permitted_use=True, basis='Generated synthetic test fixture', redistribution_permitted=False),
        video_sha256='0'*64, teams={'A': 'positive_x', 'B': 'negative_x'},
        team_assignments={'s:1': dict(team_id='A', source_method='manual_review'),
                          's:2': dict(team_id='B', source_method='manual_review')},
        calibration=dict(frame_id=0, image_points_px=pixels, pitch_points_m=points,
                         landmark_names=['synthetic TL', 'synthetic TR', 'synthetic BR', 'synthetic BL']),
        camera_review=dict(source_method='manual_review', reviewed_by='synthetic test',
            continuous_no_cuts_or_replays=True, static_camera=True, notes='Generated fixed blank frames',
            max_error_px=3., checks=[dict(frame_id=i, image_points_px=pixels, pitch_points_m=points)
                                    for i in (0, 2)]),
        detector=dict(confidence_threshold=.1), tracker=dict(activation_threshold=.25, lost_track_buffer=30),
        short_track_min_frames=3)


def observations():
    tracker = SegmentTracker('s', fps=10.)
    rows, frames = [], []
    for i in range(3):
        ds = [] if i == 1 else [dict(bbox=[155, 80, 165, 110], detector_confidence=.9),
                                dict(bbox=[205, 80, 215, 110], detector_confidence=.8)]
        rows.extend(tracker.update(i, i/10, ds))
        frames.append(dict(frame_id=i, timestamp_s=i/10, detection_count=len(ds)))
    return rows, frames


def test_source_to_existing_spatial_engine_numeric_and_missingness():
    c = config()
    rows, frames = observations()
    source = build_source_rows(rows, c, fit_calibration(c['calibration']))
    assert source.schema == SOURCE_SCHEMA
    tables = integrate_source(source, c, fps=10.)
    canonical, player_frames, team_frames, frame_quality, players, teams = tables
    assert canonical.num_rows == 4
    assert all(r['player_id'] is None for r in canonical.to_pylist())
    assert set(canonical['frame_id'].to_pylist()) == {0, 2}
    p = players.to_pylist()[0]
    assert p['tracking_avg_x_m'] == pytest.approx(30., abs=1e-5)
    assert p['tracking_avg_y_m'] == pytest.approx(20., abs=1e-5)
    assert p['tracking_halfspace_occupancy'] == 1.
    assert p['mean_nearest_opponent_distance_m'] == pytest.approx(10., abs=1e-5)
    assert p['mean_nearest_teammate_distance_m'] is None
    assert p['expected_frames'] is p['visible_fraction'] is None
    q = quality_summary(source, frames, fps=10., short_track_min_frames=3)
    assert q['total_frames_processed'] == 3 and q['total_detections'] == 4
    assert q['zero_detection_frame_ids'] == [1]
    assert q['inside_pitch_fraction'] == 1.
    assert q['unique_track_ids'] == 2 and q['median_track_length_frames'] == 2
    assert q['short_track_count'] == 2


def test_out_of_bounds_and_unassigned_flags_survive_before_failure():
    c = config()
    rows, frames = observations()
    rows[0]['ground_px_x'] = 1000.
    c['team_assignments'] = {}
    source = build_source_rows(rows, c, fit_calibration(c['calibration']))
    q = quality_summary(source, frames, fps=10., short_track_min_frames=3)
    assert q['out_of_bounds_count'] == 1 and q['missing_team_assignment_count'] == 4
    with pytest.raises(ValueError, match='team'):
        integrate_source(source, c, fps=10.)


@pytest.mark.parametrize('field,value', [('segment_end_frame', 301), ('period', True),
    ('segment_start_frame', -1), ('period_time_at_segment_start_s', float('nan'))])
def test_invalid_segment_config(field, value):
    c = config()
    c[field] = value
    with pytest.raises(ValueError):
        validate_config(c, fps=10., frame_count=1000)


def test_review_required_and_cut_drift_rejected():
    c = config()
    for key in ('continuous_no_cuts_or_replays', 'static_camera'):
        bad = deepcopy(c)
        bad['camera_review'][key] = False
        with pytest.raises(ValueError):
            validate_config(bad, fps=10., frame_count=10)
    c['camera_review']['checks'] = c['camera_review']['checks'][:1]
    with pytest.raises(ValueError, match='endpoint'):
        validate_config(c, fps=10., frame_count=10)


def test_rights_gate():
    c = config()
    c['rights']['permitted_use'] = False
    with pytest.raises(ValueError, match='rights'):
        validate_config(c, fps=10., frame_count=10)


def test_unfilled_template_rejected():
    c = config() | {'template_only': True}
    with pytest.raises(ValueError, match='template'):
        validate_config(c, fps=10., frame_count=10)


def test_track_namespace_changes_when_processing_settings_change():
    from src.video_tracking.pipeline import segment_scope
    c = config()
    original = segment_scope(c, fps=10.)
    assert original == segment_scope(deepcopy(c), fps=10.)
    c['detector']['confidence_threshold'] = .5
    assert original != segment_scope(c, fps=10.)
    c = config()
    c['tracker']['activation_threshold'] = .5
    assert original != segment_scope(c, fps=10.)
    c = config()
    c['team_assignments'] = {}
    assert original == segment_scope(c, fps=10.)


def test_input_storage_rejects_nonignored_and_tracked_paths_before_io():
    from src.video_tracking.pipeline import validate_video_storage, ROOT
    with pytest.raises(ValueError, match='ignored'):
        validate_video_storage(ROOT/'public_clip.mp4')
    with pytest.raises(ValueError, match='ignored|tracked'):
        validate_video_storage(ROOT/'README.md')
    # Path gate only, no nonexistent video is opened or represented as real input.
    assert validate_video_storage(ROOT/'data/raw/video/not_downloaded.mp4') == ROOT/'data/raw/video/not_downloaded.mp4'


def make_video(path):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10., (640, 360))
    assert writer.isOpened()
    for _ in range(3):
        writer.write(np.zeros((360, 640, 3), dtype=np.uint8))
    writer.release()


def test_actual_decoder_frame_ids_timestamps_and_segment_bounds(tmp_path):
    path = tmp_path/'decoder_fixture.avi'
    make_video(path)
    frames = list(decode_segment(path, start_frame=1, end_frame=3, fps=10., start_timestamp_s=42.))
    assert [r[0] for r in frames] == [1, 2]
    assert [r[1] for r in frames] == [42., 42.1]
    assert all(r[3].shape == (360, 640, 3) for r in frames)
    with pytest.raises(ValueError, match='ended'):
        list(decode_segment(path, start_frame=0, end_frame=4, fps=10., start_timestamp_s=0.))


def test_reports_without_input_are_blocked_not_fake_zero_measurements(tmp_path):
    write_blocked_report(tmp_path, reason='NO RIGHTS-CLEARED INPUT')
    q = json.loads((tmp_path/'quality_summary.json').read_text(encoding='utf-8'))
    assert q['real_video_e2e'] == 'BLOCKED'
    assert q['total_frames_processed'] is None
    for name in ('pipeline_report.md', 'canonical_schema_check.md', 'dependency_licenses.csv'):
        assert (tmp_path/name).is_file()


def test_protected_and_nonempty_output_refused(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match='output'):
        prepare_output(repo/'outputs/spatial_feature_engine_v1/new', has_video=False)
    (tmp_path/'quality_summary.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='nonempty'):
        prepare_output(tmp_path, has_video=False)


def test_real_run_requires_ignored_local_output_even_when_rights_permit(tmp_path):
    with pytest.raises(ValueError, match='ignored'):
        prepare_output(tmp_path/'public_rows', has_video=True)


def test_detector_failure_writes_report_and_no_canonical(tmp_path, monkeypatch):
    # Only inference is replaced: exercising decode, rights, error/report plumbing.
    from src.video_tracking import pipeline
    path = tmp_path/'decoder_fixture.avi'
    make_video(path)
    c = config()
    c['video_sha256'] = sha256(path.read_bytes()).hexdigest()
    class BrokenDetector:
        def __init__(self, **kwargs):
            raise RuntimeError('test inference unavailable')
    monkeypatch.setattr(pipeline, 'PersonDetector', BrokenDetector)
    # Temporary numerical failure-report directory; no real frames can be emitted.
    monkeypatch.setattr(pipeline, 'prepare_output', lambda path, **kwargs: Path(path))
    result = run_video(path, c, tmp_path/'result')
    assert result['status'] == 'FAIL'
    assert 'test inference unavailable' in result['failure_reason']
    assert not (tmp_path/'result/canonical_tracking_rows.parquet').exists()


def test_partial_empty_frames_preserved_when_detector_later_fails(tmp_path, monkeypatch):
    from src.video_tracking import pipeline
    path = tmp_path/'decoder_fixture.avi'
    make_video(path)
    c = config()
    c['video_sha256'] = sha256(path.read_bytes()).hexdigest()
    class FailSecondFrame:
        metadata = {'input': 'synthetic_detector_stub'}
        def __init__(self, **kwargs):
            self.calls = 0
        def detect(self, frame):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError('second-frame failure')
            return []
    monkeypatch.setattr(pipeline, 'PersonDetector', FailSecondFrame)
    monkeypatch.setattr(pipeline, 'prepare_output', lambda path, **kwargs: Path(path))
    result = run_video(path, c, tmp_path/'result')
    assert result['status'] == 'FAIL'
    assert result['total_frames_processed'] == 1
    assert result['zero_detection_frame_ids'] == [0]
    assert pq.read_table(tmp_path/'result/video_tracking_rows.parquet').num_rows == 0


def test_cli_no_video_self_check_is_separate_from_real_video(tmp_path):
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-m', 'src.analysis.video_tracking_mvp',
        '--self-check', '--output', str(tmp_path/'reports')], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 2, result.stderr
    q = json.loads((tmp_path/'reports/quality_summary.json').read_text(encoding='utf-8'))
    assert q['real_video_e2e'] == 'BLOCKED' and q['total_frames_processed'] is None
    assert q['synthetic_validation']['spatial_engine_integration'] == 'PASS'
    assert q['synthetic_validation']['canonical_tracking_rows'] == 4
    assert not list((tmp_path/'reports').glob('*.parquet'))


@pytest.mark.parametrize('unassigned', [False, True])
def test_orchestration_preserves_rows_and_emits_features_only_when_valid(tmp_path, monkeypatch, unassigned):
    from src.video_tracking import pipeline
    path = tmp_path/'decoder_fixture.avi'
    make_video(path)
    c = config()
    c['video_sha256'] = sha256(path.read_bytes()).hexdigest()
    scope = pipeline.segment_scope(c, fps=10.)
    c['team_assignments'] = {} if unassigned else {
        scope+':1': dict(team_id='A', source_method='manual_review'),
        scope+':2': dict(team_id='B', source_method='manual_review')}
    class PrescribedDetections:
        metadata = {'input': 'SYNTHETIC_PRESCRIBED_BOXES_NOT_REAL_VIDEO_TEST'}
        def __init__(self, **kwargs):
            self.calls = 0
        def detect(self, frame):
            self.calls += 1
            return [] if self.calls == 2 else [dict(bbox=[155., 80., 165., 110.], detector_confidence=.9),
                                               dict(bbox=[205., 80., 215., 110.], detector_confidence=.8)]
    monkeypatch.setattr(pipeline, 'PersonDetector', PrescribedDetections)
    monkeypatch.setattr(pipeline, 'prepare_output', lambda path, **kwargs: Path(path))
    result = run_video(path, c, tmp_path/'result')
    assert pq.read_table(tmp_path/'result/video_tracking_rows.parquet').num_rows == 4
    assert result['total_frames_processed'] == 3
    if unassigned:
        assert result['status'] == 'FAIL'
        assert result['missing_team_assignment_count'] == 4
        assert not (tmp_path/'result/canonical_tracking_rows.parquet').exists()
    else:
        assert result['status'] == 'PASS', result.get('failure_reason')
        assert result['canonical_tracking_rows'] == 4
        assert (tmp_path/'result/pitch_debug.png').is_file()
        assert (tmp_path/'result/frame_000000.jpg').is_file()
        table = pq.read_table(tmp_path/'result/spatial_features.parquet')
        assert table['poorly_supported'].to_pylist() == [True, True]
        assert (tmp_path/'result/spatial_features.csv').is_file()
