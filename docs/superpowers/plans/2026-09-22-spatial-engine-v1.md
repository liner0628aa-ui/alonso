# Spatial Feature Engine v1 implementation plan

**Goal:** Implement the user's Step 3 deterministic canonical-tracking → spatial-feature specification on `feature/spatial-engine-v1`.

**Architecture:** Arrow tables match the existing repository representation; NumPy handles small per-frame pairwise matrices. Canonical x_m/y_m use a shared stadium frame in 105×68 metres, with explicit per-team/per-period attacking direction. Player-frame outputs add team-relative coordinates; distances always use the shared frame. Provider parsing remains in its adapter.

**Constraints:** No previous code or research output changes. No event inference, CV, ML, coach analysis, or new dependencies. The user's requested existing branch and completed implementation take precedence over workflow defaults for new worktrees or further design-approval stages.

## Decisions and review focus

- Rotate both axes by 180° for negative-x attacks so y=0 remains attacking left.
- Require finite numeric timestamps and complete finite coordinate pairs or two NULLs. Reject duplicate frame tracks, conflicting identities, incoherent frame clocks, unknown direction, and gross out-of-pitch coordinates.
- Keep missing/extrapolated/unknown-visible observations; only visible and detected finite positions contribute. Use a documented 0.1m boundary tolerance, flag tolerated overshoots, and exclude them from geometry without clipping.
- Use equal-frame means/shares on an explicitly supplied regular sampling grid. Reject off-grid timestamps; missing grid points remain missing. No gap interpolation or duration weighting across unobserved time.
- Known expected-frame denominators require explicit per-identity eligibility counts for the selected window; do not infer full-window participation from detection alone.
- Group by match/period/team and player ID when known; otherwise by track ID. Do not merge unrelated anonymous tracks or double count a known player in one frame.
- Width/depth default threshold: at least 3 valid visible team players; these are observed-subset extents, not complete-team compactness.

## Task 1 — schema, coordinates and exact geometry

- [x] Write `tests/test_spatial.py` with the specified 3–4–5 geometry, both attack directions, explicit zones/counts/extents, nulls, duplicates, empty input, anonymous IDs and incomplete visibility.
- [x] Run `.venv/bin/python -m pytest tests/test_spatial.py -q` and verify the missing implementation fails.
- [x] Add `src/spatial/{__init__,coordinates,features}.py`; expose canonical Arrow validation, player/team frame features, and regular-grid window aggregation.
- [x] Run the focused tests and resolve failures against hand-calculated expectations.

## Task 2 — open source adapter and reproducible smoke report

- [x] Inspect pinned official SkillCorner README, license, metadata and coordinate diagram; verify directions from documented metadata rather than player geometry.
- [x] Test `src/data/sources/skillcorner_tracking.py` with small provider-shaped fixtures, preserving detection flags and requiring explicit direction semantics.
- [x] Download only a bounded JSONL prefix into ignored `data/raw/spatial_skillcorner`; record immutable URL, SHA256 and exact frame/time slice.
- [x] Add `src/analysis/spatial_engine_report.py` to produce feature CSVs, coverage summary, exact dictionary, validation report, compatibility note and one static pitch plot. No raw file enters version control.

## Task 3 — validation and final review

- [x] Validate distances, extents, occupancy sums, finite values and every metric's denominator on the real slice; report runtime.
- [x] Run `.venv/bin/python -m pytest -q` including all existing tests.
- [x] Review interfaces, invalid/empty input, multi-team coordinate invariance, eligibility denominators, and reproducibility.
- [x] Compare all original tracked-file hashes against the pre-write snapshot; report protected files unchanged and stop at deterministic features.

## Execution record

- Core: 27 initial geometry/coverage tests passed after missing-module failure.
- Adapter: 7 provider mapping tests passed after missing-module failure.
- Independent review: reproduced and fixed duplicate sampling slots, colliding custom-radius column names, and conflated team frame availability/visibility; 3 regression tests passed.
- Report: 7 sanity/dictionary tests passed after missing-module failure.
- Real integration: pinned SkillCorner match 1886347, 300 frames / 30 seconds; 6,600 player rows and 3,993 valid observations. Geometry sanity PASS.
- Second independent review found no further material issues in adapter, report or compatibility definitions.
- Full suite: 127 passed, 20 subtests passed, 0 failed. All 120 original tracked files remain byte-identical.
- Ruling: use known source roster eligibility for the sample's expected_frames; unknown eligibility remains NULL in the general engine. Canonical standardization of the 104m source pitch is disclosed, not treated as exact ground-distance preservation.
- Ruling: use direct inline task execution on the explicitly requested clean feature branch; no commits, merges, previous-artifact regeneration or external publication are needed for this deliverable.
