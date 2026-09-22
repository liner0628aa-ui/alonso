"""CLI and explicitly synthetic component checks; no footage fallback."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

from src.video_tracking.calibration import fit_calibration, transform_points
from src.video_tracking.detection import PersonDetector
from src.video_tracking.tracking import SegmentTracker
from src.video_tracking.pipeline import (ROOT, prepare_output, run_video, write_blocked_report,
    write_reports, build_source_rows, quality_summary, integrate_source)


def synthetic_check():
    """Prescribed boxes and known geometry: never label this real video E2E."""
    pitch = np.array([[0., 0.], [105., 0.], [105., 68.], [0., 68.],
                      [16.5, 13.84], [16.5, 54.16], [52.5, 0.], [52.5, 68.]])
    image = pitch*5+[10., 10.]
    c = dict(frame_id=0, image_points_px=image.tolist(), pitch_points_m=pitch.tolist(),
             landmark_names=[f'synthetic_point_{i}' for i in range(8)])
    calibration = fit_calibration(c)
    predicted, _ = transform_points(calibration, np.array([[160., 110.], [210., 110.]]))
    maximum_error = float(np.max(np.linalg.norm(predicted-[[30., 20.], [40., 20.]], axis=1)))
    if maximum_error > 1e-4:
        raise ValueError('Synthetic homography error exceeds 0.0001m')
    config = dict(match_id='SYNTHETIC_CONTRACT_ONLY', period=1, segment_start_frame=0, segment_end_frame=3,
        period_time_at_segment_start_s=0., teams={'A': 'positive_x', 'B': 'negative_x'},
        team_assignments={'synthetic:1': dict(team_id='A', source_method='manual_review'),
                          'synthetic:2': dict(team_id='B', source_method='manual_review')})
    tracker = SegmentTracker('synthetic', fps=10.)
    observations, frames = [], []
    for frame in range(3):
        detections = [] if frame == 1 else [dict(bbox=[155., 80., 165., 110.], detector_confidence=.9),
                                           dict(bbox=[205., 80., 215., 110.], detector_confidence=.8)]
        observations.extend(tracker.update(frame, frame/10., detections))
        frames.append(dict(frame_id=frame, timestamp_s=frame/10., detection_count=len(detections)))
    source = build_source_rows(observations, config, calibration)
    tables = integrate_source(source, config, fps=10.)
    a = next(r for r in tables[4].to_pylist() if r['team_id'] == 'A')
    if (tables[0].num_rows != 4 or abs(a['tracking_avg_x_m']-30) > 1e-4 or
            abs(a['tracking_avg_y_m']-20) > 1e-4 or a['tracking_halfspace_occupancy'] != 1 or
            abs(a['mean_nearest_opponent_distance_m']-10) > 1e-4 or
            a['mean_nearest_teammate_distance_m'] is not None or a['visible_fraction'] is not None):
        raise ValueError('Synthetic Spatial Engine contract mismatch')
    return dict(evidence_type='SYNTHETIC_PRESCRIBED_BOXES_NOT_VIDEO',
        person_detector_used=False, tracker=tracker.metadata, calibration=calibration,
        max_independent_query_error_m=maximum_error,
        spatial_engine_integration='PASS', canonical_tracking_rows=tables[0].num_rows,
        quality=quality_summary(source, frames, fps=10., short_track_min_frames=3),
        example_player_window=a,
        interpretation='Software/geometry contract only; not a measurement accuracy or tactical result.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path, default=Path('outputs/video_tracking_mvp'))
    parser.add_argument('--review-only', action='store_true', help='Generate local track review frames, no canonical export')
    parser.add_argument('--self-check', action='store_true', help='Run explicitly synthetic geometry/tracking/engine checks without footage')
    parser.add_argument('--detector-smoke', action='store_true', help='Run pretrained inference on one generated blank image, not video validation')
    args = parser.parse_args(argv)
    try:
        if args.video is not None:
            if args.config is None or args.self_check or args.detector_smoke:
                raise ValueError('--video requires --config and cannot be mixed with synthetic checks')
            config = json.loads(args.config.read_text(encoding='utf-8-sig'))
            summary = run_video(args.video, config, args.output, review_only=args.review_only)
            print(json.dumps({k: summary.get(k) for k in ('status', 'real_video_e2e', 'failure_reason',
                'total_frames_processed', 'total_detections', 'unique_track_ids', 'canonical_tracking_rows')}, indent=2))
            return 0 if summary['status'] == 'PASS' else 2 if summary['status'] == 'REVIEW_REQUIRED' else 1
        if args.review_only or args.config is not None:
            raise ValueError('--review-only and --config require --video')
        output = prepare_output(args.output, has_video=False)
        summary = write_blocked_report(output, reason='NO RIGHTS-CLEARED INPUT')
        if args.self_check:
            summary['synthetic_validation'] = synthetic_check()
        if args.detector_smoke:
            detector = PersonDetector(cache_dir=ROOT/'data/raw/video/model_cache')
            rows = detector.detect(np.zeros((360, 640, 3), dtype=np.uint8))
            summary['detector_smoke'] = dict(evidence_type='GENERATED_BLANK_IMAGE_NOT_VIDEO',
                inference_executed=True, accuracy_evaluated=False, person_detections=len(rows), metadata=detector.metadata)
        write_reports(output, summary)
        if args.self_check:
            with (output/'canonical_schema_check.md').open('a', encoding='utf-8') as f:
                f.write('\nSynthetic prescribed-box adapter -> existing Spatial Engine: PASS. '
                        'See synthetic_validation in quality_summary.json. Real video: NOT RUN.\n')
        print('REAL VIDEO E2E: BLOCKED - NO RIGHTS-CLEARED INPUT')
        if args.self_check:
            print('SYNTHETIC GEOMETRY / BYTETRACK / SPATIAL ENGINE CONTRACT: PASS')
        return 2
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
