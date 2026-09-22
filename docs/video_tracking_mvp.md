# Broadcast video to pitch coordinates MVP

This milestone measures feasibility, not tactics. It adds an adapter to the existing
Spatial Feature Engine v1 without changing that engine. No rights-cleared broadcast
video was supplied. Real-video end-to-end measurement is **BLOCKED**; synthetic
contract results and generated-blank-image detector execution are separate evidence.

## Install and verify

Python 3.12 was used on Windows. Existing requirements are unchanged; the optional
video stack is pinned in `requirements-video.txt`. Create an isolated environment
and install that file. First detector use downloads the official pretrained weights
to ignored `data/raw/video/model_cache/`; further runs verify their SHA-256 locally.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-video.txt
$env:MPLBACKEND = 'Agg'
.venv/Scripts/python.exe -X utf8 -m pytest -q
```

`-X utf8` is needed for existing code reading UTF-8 files on a Korean Windows locale.
`MPLBACKEND=Agg` avoids the existing explorer test requiring a GUI/Tcl installation.
These are environment settings, not changes to protected code.

To reproduce component evidence without footage, choose a fresh output directory:

```powershell
.venv/Scripts/python.exe -X utf8 -m src.analysis.video_tracking_mvp --self-check --detector-smoke --output outputs/video_tracking_mvp/component_check
```

Exit **2** means the real-video run is BLOCKED. `synthetic_validation` contains
measured contract checks from prescribed boxes and known geometry; `detector_smoke`
records actual pretrained inference on a generated blank image. Neither establishes
detector accuracy, player tracking quality, or real-video feasibility. No synthetic
sample is saved with a real-match filename. Without these flags, no-input mode only
writes the four required blocked reports and leaves real measurement counts NULL.

## One permitted continuous clip

1. Put a legally usable clip under ignored `data/raw/video/`. No downloading from
   protected streams or circumventing access controls. Use one manually reviewed
   continuous camera segment of **20–30 seconds** for real validation. The runner
   accepts shorter diagnostic segments but never more than 30 seconds per run.
2. Copy `config/video_sample.template.json` to `data/raw/video/sample_config.json`.
   Fill all applicable fields from the actual clip; set `template_only` to false.
   Do not treat the empty template as measured calibration or permission.
3. Hash that exact file with `(Get-FileHash -Algorithm SHA256
   data/raw/video/sample.mp4).Hash.ToLowerInvariant()` and enter `video_sha256`.
   Record a concrete permission/license basis, reviewer, explicit teams and attack
   directions, and confirmation of no cuts/replays throughout the chosen segment.
4. `segment_start_frame` is inclusive and `segment_end_frame` exclusive, using
   zero-based original decoded frames. `period_time_at_segment_start_s` is the
   supplied match-period clock at the first selected frame; it is not inferred
   from a broadcast clock or score graphic. Explain any uncertain synchronization
   in the review notes. IDs include the video hash, segment label, boundaries and
   a signature of detector/tracker settings and package versions. Changing these
   settings invalidates old manual mappings; perform review again.
5. Run review mode to obtain observed boxes, track IDs and local annotated images.
   It does not require completed calibration, static-camera confirmation or team
   assignments. It still requires video rights, explicit directions and review of
   the continuous segment. Use a fresh output directory:

```powershell
.venv/Scripts/python.exe -X utf8 -m src.analysis.video_tracking_mvp --video data/raw/video/sample.mp4 --config data/raw/video/sample_config.json --review-only --output outputs/video_tracking_mvp_local/review_01
```

Review mode exits 2 (`REVIEW_REQUIRED`). Images include first/last frames and first
appearances of new tracks; the numerical source table contains all retained
detections. Review the original segment too: a first appearance cannot establish
that a track never switches identity. If a track changes team, split/reselect the
segment or explicitly exclude it with a reason; do not silently reassign it midway.

6. Fill `team_assignments` using the full IDs in `track_summary.json`. For example,
   the *structure* of an entry is:

```json
{
  "teams": {"home": "positive_x", "away": "negative_x"},
  "team_assignments": {
    "ACTUAL_TRACK_ID_FROM_REVIEW": {"team_id": "home", "source_method": "manual_review"},
    "ACTUAL_NONPLAYER_TRACK_ID": {"exclude": true, "reason": "referee reviewed in clip", "source_method": "manual_review"}
  }
}
```

These direction values are examples, not assumptions about the clip. Supply actual
directions. Goalkeepers can be manually assigned to their teams. Referees, staff
and spectators must be explicitly excluded. No jersey or named-player identity is
inferred. Every tracked, nonexcluded person needs a label; unknown or stale labels
block canonical export. Detections that ByteTrack has not assigned an ID remain
in the source table with NULL track_id, counted in QC, and cannot enter the engine.

7. Enter at least four distinct non-collinear image/pitch correspondences at
   `calibration.frame_id`; with exactly four, no three can be collinear. Use named,
   unambiguous line intersections, never guessed player positions. Image coordinates
   use **original frame pixels**, origin top-left. Pitch coordinates use the shared
   **canonical 105x68m** reference, x right and y down. If measured pitch dimensions
   differ, explicitly scale actual landmark coordinates to this reference and record
   that assumption. Do not assume the penalty-area dimensions remain unscaled after
   rescaling a non-105x68 pitch. Document unknown actual pitch dimensions.
8. Confirm `static_camera=true` only after reviewing the whole segment. Supply
   `camera_review.checks` at the first and last selected frames (and optionally
   intermediate frames). Each check has `frame_id`, at least four spatially spread
   `image_points_px` and the corresponding `pitch_points_m`, independently clicked
   in that frame. Do not copy image positions from the calibration frame. Endpoint
   reprojection error above `max_error_px` fails the run. Material pan/zoom or any
   cut/replay requires a new segment/calibration; there is no automatic compensation.

Then the reproducible processing command is:

```powershell
.venv/Scripts/python.exe -X utf8 -m src.analysis.video_tracking_mvp --video data/raw/video/sample.mp4 --config data/raw/video/sample_config.json --output outputs/video_tracking_mvp_local/run_01
```

Exit 0 means the measurement pipeline and canonical/engine contracts passed, not
that player coordinates are independently accurate. Exit 1 means failure: inspect
`quality_summary.json`. Config/hash/rights/calibration failures stop before inference;
source rows and frame ledger are preserved if a later step fails. Existing output
directories are never overwritten. Reproduction therefore uses a fresh directory.

Repository-local input footage must also be untracked and git-ignored; this is
checked before opening it. External user-provided permitted clips can be read
in place, but all generated media and rows still go to ignored local output.

## Measurement contract and diagnostics

- **Detector:** TorchVision SSDLite320 MobileNet V3 Large, `COCO_V1`, CPU. No training.
  Scores are retained exactly; thresholds, package/weight versions, hash, CPU device
  and inference runtime are recorded. Its small input resolution is a practical
  limitation for distant broadcast players; no accuracy is claimed.
- **Tracking:** mature Supervision ByteTrack, no re-identification across segments.
  It consumes every decoded frame, including empty frames. The adapter returns
  observed detector boxes only, never Kalman-predicted locations. Track support
  includes start/end, number of observations, time span, `observed_frames/fps`
  observed duration, and mean detector confidence. Time span can include gaps.
- **Ground point:** `((x_min+x_max)/2, y_max)`. Pose, occlusion, truncated feet,
  goalkeeper dives, camera perspective and bounding-box error can displace it.
- **Calibration:** OpenCV estimates pitch-to-image homography so RANSAC residuals
  and thresholds are in **pixels**, then inverts it for ground points. Report all
  residuals plus inlier-only mean/median/max. Reject insufficient consensus, singular
  or nearly collinear geometry, crossed projective horizons and excessive inlier
  residual. The default 2px RANSAC / 3px acceptance thresholds are configurable QC
  choices, not statistically calibrated uncertainty. Four points can fit exactly
  even when manually wrong. Independent endpoint checks also do not bound player
  position error or rule out transient drift between checks.
  Small coordinate errors near zone/distance thresholds can change classifications.
- **Layers:** source parquet preserves raw boxes, detector score, pixel ground point,
  manual team method/exclusion, homography ID, raw x/y, reprojection diagnostic,
  out-of-bounds/hull flags and track support. Canonical parquet uses the existing
  engine schema exactly; player_id and both confidence fields are NULL. Confidence
  is not inferred from scores, fit residuals or number of observations.
- **Time:** require consistent decoder frame positions and presentation-time
  increments before putting coordinates onto the engine's regular sampling grid.
  Variable-rate or missing presentation clocks fail, rather than being silently
  treated as uniformly sampled time. All original frame IDs remain unchanged.
- **Quality:** total frames/detections, detections per frame, unique IDs, median
  observed track length, zero-detection frames, coordinate min/max and in-pitch
  fraction use the actual source table. Out-of-bounds points are flagged, never
  clipped. Canonical validator rejects beyond its existing tolerance; tolerated
  overshoots are excluded by the unchanged engine. A short-track threshold of 3
  observed frames is a disclosed diagnostic, not a tactical validity threshold.
- **Features:** existing player/frame/window and team/frame/window functions run
  unchanged. Output feature tables explicitly carry `poorly_supported=true` and
  `support_reason=incomplete_broadcast_visibility`, in addition to engine support
  counts. Player eligible-frame counts and coverage remain NULL because the
  complete roster/visibility are unknown. Team extents require the engine's existing
  minimum count, but still describe only the visible subset. Empty video frames
  are retained in `frame_ledger.json`; no (0,0) players are invented for them.

## Files, permissions and licenses

Detailed rows, raw footage, weights, annotated frames and pitch plots always stay
in git-ignored local paths, including when redistribution is permitted. Publication
is a separate, deliberate numerical-only selection after rights review. No copied
broadcast imagery is included in the repository. The public no-input report contains
only component evidence and a BLOCKED real-video status.

The package/version/license/purpose inventory is
`outputs/video_tracking_mvp/dependency_licenses.csv`. Upstream sources were inspected
before installation. [TorchVision code](https://github.com/pytorch/vision/blob/main/LICENSE)
is BSD-3-Clause; its [pretrained model notice](https://github.com/pytorch/vision#pre-trained-model-license)
explicitly distinguishes dataset/model terms. COCO source images have their own
rights; this work does not redistribute images or weights or assert blanket rights.
[Supervision 0.27.0](https://github.com/roboflow/supervision/blob/0.27.0/LICENSE.md)
is MIT. [OpenCV packaging](https://github.com/opencv/opencv-python/blob/master/LICENSE.txt)
and its bundled third-party notices must be retained; core OpenCV uses Apache-2.0.
[Ultralytics](https://www.ultralytics.com/license) was considered and not installed
because no AGPL project licensing decision or Enterprise license exists here.
The repository has no top-level project LICENSE; upstream license review is not a
new project license or a legal opinion authorizing arbitrary distribution.

Stop here: no ball tracking, OCR, named-player recognition, automated pitch-keypoint
network, events, full matches, neural representation training, or club/coach claims.
