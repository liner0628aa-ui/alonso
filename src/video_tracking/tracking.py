"""ByteTrack wrapper: output observed boxes only; preserve untracked detections."""
from collections import defaultdict
import importlib.metadata

import numpy as np

from .detection import ground_point


class SegmentTracker:
    def __init__(self, segment_id, *, fps, activation_threshold=.25, lost_track_buffer=30):
        import supervision as sv
        if not isinstance(segment_id, str) or not segment_id.strip():
            raise ValueError('Explicit segment scope required')
        if isinstance(fps, bool) or not np.isfinite(fps) or fps <= 0:
            raise ValueError('Positive finite fps required')
        if not np.isfinite(activation_threshold) or not 0 < activation_threshold < .9:
            raise ValueError('Invalid activation threshold')
        if isinstance(lost_track_buffer, bool) or not isinstance(lost_track_buffer, int) or lost_track_buffer < 1:
            raise ValueError('Positive lost_track_buffer required')
        self.sv, self.segment_id, self.fps = sv, segment_id, fps
        self.previous_frame, self.previous_time = None, None
        self.tracker = sv.ByteTrack(track_activation_threshold=activation_threshold,
            lost_track_buffer=lost_track_buffer, frame_rate=max(1, round(fps)), minimum_consecutive_frames=1)
        self.metadata = dict(name='Supervision ByteTrack', version=importlib.metadata.version('supervision'),
            license='MIT', activation_threshold=activation_threshold, lost_track_buffer=lost_track_buffer,
            tracker_frame_rate=max(1, round(fps)), minimum_consecutive_frames=1,
            minimum_matching_threshold=.8, reidentification=False)

    def update(self, frame_id, timestamp_s, detections):
        if isinstance(frame_id, bool) or not isinstance(frame_id, int) or frame_id < 0:
            raise ValueError('Invalid frame ID')
        if isinstance(timestamp_s, bool) or not np.isfinite(timestamp_s) or timestamp_s < 0:
            raise ValueError('Invalid timestamp')
        if self.previous_frame is not None and (frame_id != self.previous_frame+1 or
                not np.isclose(timestamp_s-self.previous_time, 1/self.fps, atol=1e-7, rtol=0)):
            raise ValueError('Frames must be consecutive and timestamps monotonic on the declared grid')
        for item in detections:
            ground_point(item['bbox'])
            if not np.isfinite(item['detector_confidence']) or not 0 <= item['detector_confidence'] <= 1:
                raise ValueError('Invalid detection confidence')
        self.previous_frame, self.previous_time = frame_id, timestamp_s
        observed = self.sv.Detections(xyxy=np.array([d['bbox'] for d in detections], dtype=float).reshape(-1, 4),
            confidence=np.array([d['detector_confidence'] for d in detections], dtype=float),
            class_id=np.ones(len(detections), dtype=int), data={'input_index': np.arange(len(detections))})
        tracked = self.tracker.update_with_detections(observed)
        assigned = {int(index): f'{self.segment_id}:{int(tid)}'
                    for index, tid in zip(tracked.data.get('input_index', []), tracked.tracker_id)}
        return [dict(item, frame_id=frame_id, timestamp_s=float(timestamp_s), detection_index=i,
                     track_id=assigned.get(i), ground_px_x=ground_point(item['bbox'])[0],
                     ground_px_y=ground_point(item['bbox'])[1]) for i, item in enumerate(detections)]


def track_summary(rows, *, fps):
    groups = defaultdict(list)
    for row in rows:
        if row['track_id'] is not None:
            groups[row['track_id']].append(row)
    return [dict(track_id=tid, start_frame=min(r['frame_id'] for r in group),
        end_frame=max(r['frame_id'] for r in group), observed_frames=len(group),
        time_span_s=max(r['timestamp_s'] for r in group)-min(r['timestamp_s'] for r in group),
        observed_duration_s=len(group)/fps,
        mean_detector_confidence=float(np.mean([r['detector_confidence'] for r in group])))
        for tid, group in sorted(groups.items())]
