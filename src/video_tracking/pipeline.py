"""One reviewed static camera segment -> source rows -> unchanged Spatial Engine."""
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
from time import perf_counter

import cv2
import numpy as np
import pyarrow as pa
import pyarrow.csv as arrow_csv
import pyarrow.parquet as pq

from src.spatial.coordinates import canonical_table, finite_number
from src.spatial.features import frame_features, window_features
from .calibration import fit_calibration, transform_points, check_camera
from .detection import PersonDetector
from .team_assignment import validate_team_config, assign_team, canonical_rows
from .tracking import SegmentTracker, track_summary

ROOT = Path(__file__).resolve().parents[2]
LICENSES = ROOT/'outputs/video_tracking_mvp/dependency_licenses.csv'
SOURCE_SCHEMA = pa.schema([
    ('frame_id', pa.int64()), ('timestamp_s', pa.float64()), ('detection_index', pa.int64()),
    ('track_id', pa.string()), ('bbox', pa.list_(pa.float64(), 4)),
    ('ground_px_x', pa.float64()), ('ground_px_y', pa.float64()), ('detector_confidence', pa.float64()),
    ('team_id', pa.string()), ('team_assignment_method', pa.string()), ('excluded', pa.bool_()),
    ('exclusion_reason', pa.string()), ('homography_id', pa.string()),
    ('pitch_x_raw', pa.float64()), ('pitch_y_raw', pa.float64()),
    ('calibration_reprojection_error', pa.float64()), ('homography_failure', pa.bool_()),
    ('homography_failure_reason', pa.string()), ('outside_calibration_hull', pa.bool_()),
    ('out_of_bounds', pa.bool_()), ('missing_team_assignment', pa.bool_()),
    ('track_observed_frames', pa.int64()), ('short_track', pa.bool_()),
])
LIMITATIONS = [
    'Broadcast visible subset only; missing detection does not establish player absence.',
    'Bottom-centre bbox is a ground-contact approximation affected by pose, occlusion, camera angle and box error.',
    'Reprojection residual is landmark fit error in pixels, not player coordinate accuracy or a probability.',
    'Four exact landmarks have no redundant fit validation; extrapolation beyond their hull is flagged.',
    'Manual whole-segment static-camera review and endpoint checks cannot prove absence of between-check drift.',
    'Anonymous short tracks can fragment or switch identity; no cross-cut/replay re-identification.',
    'Person detector is not football-specific; manual review must exclude referees, staff and spectators.',
    'All spatial features describe incompletely observed players; nearest distances and team extents are poorly supported.',
    '105x68m is the canonical reference; actual pitch dimensions must be accounted for when entering landmarks.',
]


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def prepare_output(path, *, has_video):
    output = Path(path).resolve()
    if output == ROOT or ROOT.is_relative_to(output):
        raise ValueError('Unsafe output directory')
    if output.is_relative_to(ROOT):
        allowed = (ROOT/'outputs/video_tracking_mvp', ROOT/'outputs/video_tracking_mvp_local',
                   ROOT/'data/raw/video/runs')
        if not any(output == p or output.is_relative_to(p) for p in allowed):
            raise ValueError('Only video-tracking output paths may be written; protected output refused')
    if has_video:
        local_roots = (ROOT/'outputs/video_tracking_mvp_local', ROOT/'data/raw/video/runs')
        if not any(output == p or output.is_relative_to(p) for p in local_roots):
            raise ValueError('Video results must use an ignored local output path')
        check = subprocess.run(['git', '-c', f'safe.directory={ROOT.as_posix()}', 'check-ignore', '-q',
                                str(output/'frame.jpg')], cwd=ROOT, capture_output=True)
        if check.returncode != 0:
            raise ValueError('Video output must be confirmed ignored by git')
    if output.exists() and any(p.name != 'dependency_licenses.csv' for p in output.iterdir()):
        raise ValueError('Refusing nonempty output; use a new run directory')
    output.mkdir(parents=True, exist_ok=True)
    return output


def validate_config(config, *, fps, frame_count, review_only=False):
    if config.get('template_only', False) is not False:
        raise ValueError('Fill the video template from measured/reviewed input before use')
    if not finite_number(fps) or not 0 < fps <= 120:
        raise ValueError('Finite source fps in (0,120] required')
    for key in ('segment_start_frame', 'segment_end_frame', 'period'):
        v = config[key]
        if isinstance(v, bool) or not isinstance(v, int) or v < (1 if key == 'period' else 0):
            raise ValueError(f'Invalid {key}')
    start, end = config['segment_start_frame'], config['segment_end_frame']
    if not start < end <= frame_count or (end-start)/fps > 30.+1e-8:
        raise ValueError('Exactly one nonempty segment of at most 30s within the video is required')
    for key in ('match_id', 'segment_id'):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f'Explicit {key} required')
    if not finite_number(config['period_time_at_segment_start_s']) or config['period_time_at_segment_start_s'] < 0:
        raise ValueError('Explicit finite period clock at segment start required')
    rights = config['rights']
    if (rights.get('permitted_use') is not True or not isinstance(rights.get('basis'), str)
            or not rights['basis'].strip() or not isinstance(rights.get('redistribution_permitted'), bool)):
        raise ValueError('Document rights-cleared permitted use and redistribution permission')
    digest = config['video_sha256']
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Full video_sha256 ties manual review to exact input')
    review = config['camera_review']
    if (review.get('source_method') != 'manual_review' or
            review.get('continuous_no_cuts_or_replays') is not True or
            not isinstance(review.get('reviewed_by'), str) or not review['reviewed_by'].strip() or
            not isinstance(review.get('notes'), str) or not review['notes'].strip()):
        raise ValueError('Manual continuous segment review (no cuts or replays) required')
    validate_team_config(config)
    minimum = config.get('short_track_min_frames', 3)
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        raise ValueError('Positive short_track_min_frames required')
    if not review_only:
        if review.get('static_camera') is not True:
            raise ValueError('Static camera required: material pan/zoom invalidates this homography')
        if not start <= config['calibration']['frame_id'] < end:
            raise ValueError('Calibration frame must be within segment')
        checks = review.get('checks', [])
        ids = [c['frame_id'] for c in checks]
        if (not {start, end-1} <= set(ids) or len(ids) != len(set(ids)) or
                any(isinstance(i, bool) or not isinstance(i, int) or not start <= i < end for i in ids)):
            raise ValueError('Distinct endpoint camera checks within the segment are required')


def decode_segment(video, *, start_frame, end_frame, fps, start_timestamp_s):
    """Seek once; verify frame position and actual presentation-time increments."""
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError('Video decoder could not open input')
    first_pts = None
    try:
        if start_frame and not cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame):
            raise ValueError('Decoder cannot seek to segment start')
        for frame_id in range(start_frame, end_frame):
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f'Video ended before requested frame {frame_id}')
            if abs(cap.get(cv2.CAP_PROP_POS_FRAMES)-(frame_id+1)) > .1:
                raise ValueError('Decoder frame position disagrees with requested segment')
            pts = cap.get(cv2.CAP_PROP_POS_MSEC)/1000.
            if not np.isfinite(pts):
                raise ValueError('Decoder did not supply finite presentation timestamps')
            first_pts = pts if first_pts is None else first_pts
            elapsed = (frame_id-start_frame)/fps
            if abs((pts-first_pts)-elapsed) > min(.002, .05/fps):
                raise ValueError('Variable/missing decoder timestamps: regular-grid Spatial Engine window unsupported')
            yield frame_id, start_timestamp_s+elapsed, pts, frame
    finally:
        cap.release()


def validate_video_storage(video):
    video = Path(video).resolve()
    if video.is_relative_to(ROOT):
        relative = video.relative_to(ROOT).as_posix()
        command = ['git', '-c', f'safe.directory={ROOT.as_posix()}']
        tracked = subprocess.run(command+['ls-files', '--error-unmatch', '--', relative],
                                 cwd=ROOT, capture_output=True)
        ignored = subprocess.run(command+['check-ignore', '-q', '--', relative], cwd=ROOT, capture_output=True)
        if tracked.returncode == 0 or ignored.returncode != 0:
            raise ValueError('Repository-local footage must be untracked and git-ignored (data/raw/video/)')
    return video


def segment_scope(config, *, fps):
    # A changed detector/tracker can renumber identities. Never reuse old manual
    # labels just because the video and segment boundaries are unchanged.
    settings = dict(detector=config['detector'], tracker=config['tracker'], fps=fps,
                    model='ssdlite320_mobilenet_v3_large:COCO_V1', adapter_version='video-mvp-v1',
                    packages={p: version(p) for p in ('torch', 'torchvision', 'supervision', 'opencv-python')})
    signature = sha256(json.dumps(settings, sort_keys=True, allow_nan=False).encode()).hexdigest()[:12]
    return (f'{config["video_sha256"][:16]}:{config["segment_id"]}:'
            f'{config["segment_start_frame"]}-{config["segment_end_frame"]}:{signature}')


def build_source_rows(observations, config, calibration):
    counts = {}
    for r in observations:
        if r['track_id'] is not None:
            counts[r['track_id']] = counts.get(r['track_id'], 0)+1
    rows = []
    for observation in observations:
        r = assign_team(observation, config)
        r.update(homography_id=calibration['homography_id'] if calibration else None,
            pitch_x_raw=None, pitch_y_raw=None, calibration_reprojection_error=None,
            homography_failure=False, homography_failure_reason=None, outside_calibration_hull=None,
            out_of_bounds=None, track_observed_frames=counts.get(r['track_id'], 0),
            missing_team_assignment=r['track_id'] is not None and not r['excluded'] and r['team_id'] is None)
        r['short_track'] = r['track_id'] is not None and r['track_observed_frames'] < config.get('short_track_min_frames', 3)
        if calibration:
            r['calibration_reprojection_error'] = calibration['reprojection_mean_px']
            try:
                xy, outside = transform_points(calibration, [[r['ground_px_x'], r['ground_px_y']]])
                x, y = map(float, xy[0])
                r.update(pitch_x_raw=x, pitch_y_raw=y, outside_calibration_hull=bool(outside[0]),
                         out_of_bounds=not (0 <= x <= 105 and 0 <= y <= 68))
            except ValueError as exc:
                r.update(homography_failure=True, homography_failure_reason=str(exc))
        rows.append(r)
    return pa.Table.from_pylist(rows, schema=SOURCE_SCHEMA)


def quality_summary(source, frames, *, fps, short_track_min_frames):
    rows = source.to_pylist()
    tracks = track_summary(rows, fps=fps)
    valid = [r for r in rows if r['pitch_x_raw'] is not None]
    return dict(total_frames_processed=len(frames), total_detections=len(rows), unique_track_ids=len(tracks),
        median_track_length_frames=float(np.median([r['observed_frames'] for r in tracks])) if tracks else None,
        detections_per_frame=len(rows)/len(frames) if frames else None,
        zero_detection_frame_ids=[r['frame_id'] for r in frames if r['detection_count'] == 0],
        transformed_ground_points=len(valid), inside_pitch_fraction=sum(not r['out_of_bounds'] for r in valid)/len(valid) if valid else None,
        coordinate_min_max={axis: [min(r[axis] for r in valid), max(r[axis] for r in valid)] if valid else None
                            for axis in ('pitch_x_raw', 'pitch_y_raw')},
        out_of_bounds_count=sum(r['out_of_bounds'] is True for r in rows),
        homography_failure_count=sum(r['homography_failure'] for r in rows),
        outside_calibration_hull_count=sum(r['outside_calibration_hull'] is True for r in rows),
        missing_team_assignment_count=sum(r['missing_team_assignment'] for r in rows),
        untracked_detection_count=sum(r['track_id'] is None for r in rows),
        manually_excluded_detection_count=sum(r['excluded'] for r in rows),
        short_track_count=sum(r['observed_frames'] < short_track_min_frames for r in tracks),
        short_track_min_frames=short_track_min_frames)


def integrate_source(source, config, *, fps):
    if any(r['homography_failure'] for r in source.to_pylist()):
        raise ValueError('Homography failure in source rows; inspect source table')
    canonical = canonical_table(canonical_rows(source.to_pylist(), config,
                                match_id=config['match_id'], period=config['period']))
    if not canonical.num_rows:
        raise ValueError('No assigned observed tracks; Spatial Engine integration has no support')
    pf, tf, fq = frame_features(canonical)
    start = config['period_time_at_segment_start_s']
    end = start+(config['segment_end_frame']-config['segment_start_frame'])/fps
    pw, tw = window_features(pf, tf, start_s=start, end_s=end, sample_interval_s=1/fps)
    # Explicitly unknown eligibility: do not use detections to fabricate a roster.
    return canonical, pf, tf, fq, pw, tw


def write_reports(output, summary):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    license_text = LICENSES.read_text(encoding='utf-8')
    (output/'dependency_licenses.csv').write_text(license_text, encoding='utf-8')
    save_json(output/'quality_summary.json', summary)
    status = summary.get('status', 'BLOCKED')
    (output/'pipeline_report.md').write_text(
        '# Broadcast video to pitch coordinates MVP\n\n'
        f'Status: **{status}**\n\nREAL VIDEO E2E: **{summary.get("real_video_e2e", "BLOCKED")}**\n\n'
        + summary.get('failure_reason', 'Measurement feasibility only; no tactical conclusions.')+'\n\n'
        'Ground point: ((x_min+x_max)/2, y_max), in original decoded image pixels.\n\n'
        'Source uncertainty fields stay separate. Canonical confidence and player identity remain NULL.\n\n'
        + '\n'.join('- '+text for text in LIMITATIONS)+'\n\n'
        'See quality_summary.json for actual counts and run metadata. No real measurements exist when counts are NULL.\n', encoding='utf-8')
    (output/'canonical_schema_check.md').write_text(
        '# Canonical schema check\n\n'
        f'Spatial Engine integration: {summary.get("spatial_engine_integration", "NOT RUN")}\n\n'
        'Authority: src.spatial.coordinates.canonical_table, unchanged.\n'
        'Shared stadium-frame x_m/y_m on the 105x68 reference pitch; never clipped.\n'
        'Anonymous player_id=NULL; segment-scoped track_id; directions supplied per team.\n'
        'coordinate_confidence=NULL and identity_confidence=NULL; no invented probabilities.\n'
        'Unknown team blocks canonical export. Untracked and explicitly excluded people stay in source/QC.\n'
        'Frame times use configured period clock plus validated constant-rate frame offsets.\n'
        'Zero-detection frames are retained in frame_ledger.json; no fabricated coordinates.\n', encoding='utf-8')


def write_blocked_report(output, *, reason):
    summary = dict(status='BLOCKED', real_video_e2e='BLOCKED', failure_reason=reason,
                   spatial_engine_integration='NOT RUN', total_frames_processed=None,
                   total_detections=None, unique_track_ids=None, canonical_tracking_rows=None,
                   limitations=LIMITATIONS)
    write_reports(output, summary)
    return summary


def _save_debug(frame, rows, path):
    image = frame.copy()
    for row in rows:
        x1, y1, x2, y2 = map(round, row['bbox'])
        label = f'{row["track_id"] or "untracked"} {row.get("team_id") or "unassigned"}'
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 255), 1)
        cv2.circle(image, (round(row['ground_px_x']), round(row['ground_px_y'])), 3, (0, 0, 255), -1)
        cv2.putText(image, label, (x1, max(12, y1-4)), cv2.FONT_HERSHEY_SIMPLEX, .35, (0, 255, 255), 1)
    ok, encoded = cv2.imencode('.jpg', image)
    if not ok:
        raise ValueError('Debug image encoding failed')
    encoded.tofile(str(path))


def _pitch_plot(source, output):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    rows = source.to_pylist()
    first = min((r['frame_id'] for r in rows), default=0)
    fig = Figure(figsize=(10, 7))
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.plot([0, 105, 105, 0, 0], [0, 0, 68, 68, 0], color='black')
    for r in rows:
        if r['frame_id'] == first and r['pitch_x_raw'] is not None:
            x, y = r['pitch_x_raw'], r['pitch_y_raw']
            ax.scatter(x, y, marker='x' if r['out_of_bounds'] else 'o')
            ax.text(x, y, f'{r["track_id"] or "untracked"} {r["team_id"] or "unassigned"}', fontsize=6)
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.set(xlabel='canonical x (m)', ylabel='canonical y (m)', title='Broadcast estimates: visible subset only')
    fig.savefig(output/'pitch_debug.png', dpi=150)


def run_video(video, config, output, *, review_only=False):
    output = prepare_output(output, has_video=True)
    output.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    summary = dict(status='FAIL', real_video_e2e='FAIL', spatial_engine_integration='NOT RUN',
                   total_frames_processed=0, total_detections=0, canonical_tracking_rows=None, limitations=LIMITATIONS)
    observations, frames = [], []
    fps = None
    calibration = None
    try:
        video = validate_video_storage(video)
        # Reject rights before decoding or loading any model.
        if config.get('rights', {}).get('permitted_use') is not True:
            raise ValueError('NO RIGHTS-CLEARED INPUT: permitted_use must be true')
        with video.open('rb') as f:
            digest = sha256()
            for chunk in iter(lambda: f.read(1024*1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != config['video_sha256']:
            raise ValueError('Video hash differs from manually reviewed input')
        cap = cv2.VideoCapture(str(video))
        try:
            fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
            summary['video'] = dict(sha256=digest.hexdigest(), fps=fps, frame_count=count,
                width=cap.get(cv2.CAP_PROP_FRAME_WIDTH), height=cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                duration_s_from_metadata=count/fps if fps > 0 else None)
        finally:
            cap.release()
        validate_config(config, fps=fps, frame_count=count, review_only=review_only)
        save_json(output/'run_config.json', config)
        a, b = config['segment_start_frame'], config['segment_end_frame']
        scope = segment_scope(config, fps=fps)
        summary.update(segment_scope=scope, segment_duration_s=(b-a)/fps,
                       camera_review=config['camera_review'], rights=config['rights'],
                       decoder_timestamp_tolerance_s=min(.002, .05/fps))
        if not review_only:
            calibration = fit_calibration(config['calibration'])
            calibration['camera_checks'] = check_camera(calibration, config['camera_review']['checks'],
                                                         max_error_px=config['camera_review']['max_error_px'])
            summary['calibration'] = calibration
        detector = PersonDetector(threshold=config['detector']['confidence_threshold'],
                                  cache_dir=ROOT/'data/raw/video/model_cache')
        tracker = SegmentTracker(scope, fps=fps, **config['tracker'])
        summary.update(detector=detector.metadata, tracker=tracker.metadata)
        seen = set()
        for frame_id, timestamp, pts, frame in decode_segment(video, start_frame=a, end_frame=b, fps=fps,
                                            start_timestamp_s=config['period_time_at_segment_start_s']):
            detections = detector.detect(frame)
            rows = tracker.update(frame_id, timestamp, detections)
            observations.extend(rows)
            frames.append(dict(frame_id=frame_id, timestamp_s=timestamp, decoder_timestamp_s=pts,
                               detection_count=len(detections)))
            ids = {r['track_id'] for r in rows if r['track_id'] is not None}
            if frame_id in (a, b-1) or (review_only and ids-seen):
                _save_debug(frame, [assign_team(r, config) for r in rows], output/f'frame_{frame_id:06d}.jpg')
            seen.update(ids)
        source = build_source_rows(observations, config, calibration)
        pq.write_table(source, output/'video_tracking_rows.parquet')
        save_json(output/'frame_ledger.json', frames)
        save_json(output/'track_summary.json', track_summary(observations, fps=fps))
        summary.update(quality_summary(source, frames, fps=fps,
                                       short_track_min_frames=config.get('short_track_min_frames', 3)))
        unused = set(config['team_assignments'])-{r['track_id'] for r in observations}
        summary['unused_team_assignment_ids'] = sorted(unused)
        if review_only:
            summary.update(status='REVIEW_REQUIRED', real_video_e2e='BLOCKED',
                failure_reason='Review frame images and track IDs; enter team mapping, landmarks and endpoint camera checks.')
        else:
            if unused:
                raise ValueError('Team mapping contains unknown/stale track IDs; inspect source rows')
            _pitch_plot(source, output)
            tables = integrate_source(source, config, fps=fps)
            names = ('canonical_tracking_rows', 'player_frame_features', 'team_frame_features',
                     'frame_quality', 'spatial_features', 'team_window_features')
            for name, table in zip(names, tables):
                if name in ('player_frame_features', 'team_frame_features', 'spatial_features', 'team_window_features'):
                    table = table.append_column('poorly_supported', pa.array([True]*table.num_rows, type=pa.bool_()))
                    table = table.append_column('support_reason', pa.array(['incomplete_broadcast_visibility']*table.num_rows, type=pa.string()))
                pq.write_table(table, output/(name+'.parquet'))
                if name != 'canonical_tracking_rows':
                    arrow_csv.write_csv(table, output/(name+'.csv'))
            summary.update(status='PASS', real_video_e2e='PASS', spatial_engine_integration='PASS',
                           canonical_tracking_rows=tables[0].num_rows)
    except Exception as exc:
        summary.update(status='FAIL', real_video_e2e='FAIL', failure_reason=f'{type(exc).__name__}: {exc}')
        if frames and fps:
            # Preserve measured detections even if calibration/integration failed.
            source = build_source_rows(observations, config, calibration)
            pq.write_table(source, output/'video_tracking_rows.parquet')
            save_json(output/'frame_ledger.json', frames)
            save_json(output/'track_summary.json', track_summary(observations, fps=fps))
            summary.update(quality_summary(source, frames, fps=fps,
                                           short_track_min_frames=config.get('short_track_min_frames', 3)))
    summary['runtime_s'] = perf_counter()-started
    write_reports(output, summary)
    return summary
