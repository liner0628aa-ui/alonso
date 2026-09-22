# Broadcast video to pitch coordinates MVP

Approved scope: the user's Step 4 specification and approval to work in this checkout.
Execution: inline, on feature/spatial-engine-v1 as requested. No new worktree.

## Design and contracts

One manually reviewed continuous segment, at most 30 seconds. A pretrained
TorchVision person detector feeds Supervision ByteTrack. Preserve every retained
detection, including detections not assigned a track. Only measured detections,
never predicted track locations, can become coordinates. IDs include the segment.
Manual team mapping may explicitly exclude nonplayers; missing labels block export.
Player IDs remain NULL. Directions come only from configuration.

OpenCV estimates pitch-to-image homography so RANSAC thresholds and residuals
are in pixels; invert it for ground points. Reject degenerate point geometry,
insufficient consensus and excessive inlier residual. Four-point exact fitting
does not validate accuracy. Require manual camera review plus endpoint landmark
checks; significant pan/zoom fails static calibration. Label extrapolation outside
the calibration landmark convex hull. Never clip transformed coordinates.

The existing canonical validator and frame/window feature functions are unchanged.
The source table keeps confidence, calibration error and manual review separately.
Canonical confidence fields remain NULL; no calibrated confidence is invented.
Use video-frame timestamps on a validated constant-rate grid and document the
explicit period-clock offset. Zero-detection frames remain in the frame ledger.

Raw video, model cache, frames, local rows and debug plots stay ignored. No footage
is available: implement and test components, report real video BLOCKED. Synthetic
contract evidence is always labeled synthetic and never a substitute real run.

## Tasks

- [x] 1. Restore an isolated Python environment, run the unchanged full suite,
  record baseline and inspect licenses before adding the video dependencies.
- [x] 2. Add tests/test_video_calibration.py: exact four and many correspondences,
  noisy data, RANSAC outlier, degeneracy, outside-hull/pitch and drift rejection.
  Run failing tests, implement src/video_tracking/calibration.py, rerun.
- [x] 3. Add tests/test_video_tracking.py: detector output/ground point contract,
  real ByteTrack on prescribed boxes, missed frames, segment scoping, invalid
  clocks, labels and directions. Run failing tests, implement detection.py,
  tracking.py, team_assignment.py and pipeline.py, rerun.
- [x] 4. Add CLI and persistence tests: rights gates, no-input BLOCKED report,
  source-row preservation on rejection, protected/local paths, decoder timing,
  synthetic adapter-to-existing-engine numeric integration. Run failing tests,
  implement src/analysis/video_tracking_mvp.py and finish pipeline I/O.
- [x] 5. Document config/command/license inventory; generate only measured
  synthetic validation summaries and a truthful no-real-video report.
- [x] 6. Run focused and full suites, detector inference smoke without footage,
  independent review and protected-file hash comparison; record actual results.

## Review focus

1. ByteTrack can hide warmup/low-score observations: source rows must retain them.
2. Four exact landmarks alone can give deceptively zero residual: document the
   limitation, reject collinear triples and check independent endpoint landmarks.
3. Fixed homography under camera motion: reject failed endpoint checks and require
   an explicit whole-segment manual review, including no cuts or replays.
4. Invalid source rows: save QC before canonical rejection; never silently omit
   missing teams or clip out-of-bounds positions to make integration pass.
5. Output reruns and rights: refuse nonempty output, force images into ignored
   storage, and prevent every protected path from being an output target.

## Verification commands

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pytest tests/test_video_calibration.py tests/test_video_tracking.py tests/test_video_pipeline.py -q
.venv/Scripts/python.exe -m src.analysis.video_tracking_mvp --output outputs/video_tracking_mvp
```

The last command exits with status 2 when no rights-cleared clip was supplied.
It must still write the required report files. This is a documented BLOCKED result.

## Progress / rulings

- Baseline commit: 6037376128375df4d00477b0e300ee36d94b83fe.
- User explicitly approved this checkout and implementation; continue without
  repeated design/worktree approval prompts.
- Repo has no project LICENSE: record upstream licenses and obligations; do not
  claim blanket legal clearance or redistribute detector weights/footage.
- Baseline: 127 passed, 20 subtests passed after using `-X utf8` and
  `MPLBACKEND=Agg`. Initial Windows cp949/Tcl errors were environmental; existing
  source and protected files were not changed to resolve them.
- New contracts were run failing before implementation. Focused stages passed
  31, then 44, then 47 tests; final full suite: 179 passed, 20 subtests passed,
  0 failed, 0 errors (52 new tests), 2026-09-22.
- Ruling: fixed homography requires a static manually reviewed segment plus
  independent endpoint checks. Pan/zoom requires reselecting the segment;
  intermittent undetected motion remains a disclosed measurement limitation.
- Ruling: preserve every above-threshold detection, including ByteTrack warmup/
  untracked boxes. Untracked people are explicitly counted and cannot be given
  invented canonical track IDs.
- Independent review found one P2 input-storage gap. Added a failing regression,
  then rejected tracked/nonignored repository-local input footage before IO.
  External user-provided files remain allowed; all generated media stays ignored.
- Further validation rejects crossed homography horizons, preserves empty frame
  history on partial failure, refuses unfilled templates, and scopes track IDs
  to detector/tracker settings and package versions to prevent stale manual labels.
- Detector COCO weights checksum verified; actual CPU inference executed on a
  generated blank image. No broadcast footage, actual team labels, or real-video
  accuracy measurements were available. Real E2E remains BLOCKED.
- Protected paths and src/spatial compared against baseline via git diff: unchanged.
  Kept work on the requested branch without committing, merging or publishing.
