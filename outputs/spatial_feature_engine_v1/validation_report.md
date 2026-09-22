# Spatial Feature Engine v1 — validation report

## Result and real sample

PASS: deterministic canonical tracking → player/frame/window and team/frame/window features.
The source is [SkillCorner Open Data](https://raw.githubusercontent.com/SkillCorner/opendata/4340d274572876239c154c90bc507a9b3250a656/README.md), pinned to `4340d274572876239c154c90bc507a9b3250a656`.
Published repository [MIT license](https://raw.githubusercontent.com/SkillCorner/opendata/4340d274572876239c154c90bc507a9b3250a656/LICENSE) inspected before use; attribution: SkillCorner.
The full notice is retained in SKILLCORNER_LICENSE.txt. No footage was downloaded or processed.
These are provider broadcast estimates, **not independently established tracking ground truth**.
The exact synthetic geometry tests provide the reference answers; the real slice tests integration.

- Match 1886347: Auckland FC vs Newcastle United Jets FC, 2024-11-30.
- File: `data/matches/1886347/1886347_tracking_extrapolated.jsonl`.
- Slice: period 1, source match-clock `[0.0,30.0)` seconds, frame IDs 10–309 inclusive, 300 frames at 10Hz.
- Raw acquisition: only bytes 0–1048575 (1 MiB); incomplete last JSONL line ignored, pre-match empty/unclocked frames excluded explicitly.
- 2 teams; 22 tracked identities; 6600 input player rows.
- 3993 valid detected-visible positions; all other rows retained with NULL features.
- Shared canonical coordinate min/max, including extrapolated input positions: {'x_m': [3.3620192307692283, 98.87163461538461], 'y_m': [3.3799999999999986, 67.10000000000001]}.
- Per-frame valid-visible player distribution (count: number of frames): {0: 44, 9: 32, 10: 8, 11: 29, 12: 9, 13: 9, 14: 15, 15: 2, 16: 25, 17: 3, 18: 31, 19: 28, 20: 65}.
- Core runtime: 2.307610 seconds (adapter, validation, frame and window computation; excludes I/O, plotting and source downloads).
- Sanity checks: **PASS**, 69667 finite numeric values checked; nonnegative distances/counts, pitch-bounded width/depth, occupancy sums and coverage denominators verified.
- 0 tolerated out-of-pitch rows in this slice; 0 gross-coordinate failures. No clipping or zero imputation.
- 22 player-window rows and 2 team-window rows; plot uses frame 24.

## Canonical schema and geometry

Arrow typed columns: match_id, period, timestamp_s, frame_id, team_id, nullable player_id,
required track_id, x_m, y_m, nullable visible/detected, source, nullable confidence strings,
and required attacking_direction. x_m/y_m implement the logical x/y fields in canonical metres.
Confidence strings preserve native scales/categories, without implying comparable probabilities.
The full Step 2 proposed research/event schema remains untouched; this is its deliberately minimal tracking subset.

Canonical pitch: 105×68m, shared stadium x increasing right and y increasing down.
Team-relative coordinates have x=0 own goal, x=105 opponent goal, y=0 attacking left.
For negative-x attacks **both axes rotate**: (105-x,68-y). This is a 180° rotation,
preserving handedness; x-only reflection would swap left/right tactical lanes incorrectly.
All neighbour distances use the shared frame before either team's rotation.

The provider [diagram](https://raw.githubusercontent.com/SkillCorner/opendata/4340d274572876239c154c90bc507a9b3250a656/assets/field.jpg) shows centred metre coordinates,
positive x right, positive y up. [Match metadata](https://raw.githubusercontent.com/SkillCorner/opendata/4340d274572876239c154c90bc507a9b3250a656/data/matches/1886347/1886347_match.json)
gives 104×68m and home_team_side=[right_to_left,left_to_right]. The adapter uses that
metadata, never the player arrangement, to assign directions; away directions are opposite.
Conversion: x_m=(x/104+0.5)*105, y_m=(0.5-y/68)*68.
Longitudinal standardization stretches x distances by 105/104 (about 0.96%); reported
Euclidean metres are on the canonical pitch, not exact surveyed-ground distances on this 104m pitch.

The canonical validator rejects nonnumeric clocks, nonfinite/incomplete coordinate pairs,
missing track IDs, duplicate track/player frames, conflicting identities/directions and clocks.
NULL coordinate pairs remain NULL. Out-of-bounds beyond 0.1m fails loudly; smaller
overshoots are flagged and excluded from features without clipping. Unknown visibility or
detection is excluded conservatively. Source detection is represented by `is_detected`;
the adapter maps it to detected and to the explicitly disclosed on-screen visibility proxy.

## Features and coverage

The project's explicit v1 lateral convention is left_wide [0,13.6), left_halfspace [13.6,27.2),
central [27.2,40.8), right_halfspace [40.8,54.4), right_wide [54.4,68]. This is not a universal
industry definition. Boundaries live in PitchConfig; radii are configurable and default to 5m/10m.
Inclusive radius comparisons use a 1e-9m numerical tolerance. Self is excluded.
No visible valid neighbour of a category means NULL distance **and count**; zero count means
at least one neighbour was observed but none was inside that radius.

Player windows use equal valid-frame means/shares on an explicit uniform 0.1s grid.
This is a tracking-frame/time representation, not event weighting. Off-grid or repeated sampling
slots fail; gaps are never interpolated or weighted as observed time. time_span_s is last minus
first valid timestamp, not observed duration. Windows are half-open and never mix periods.
Known player IDs group track segments; anonymous tracks remain separate. Identity switches
must be corrected or explicitly split by the provider adapter, never guessed in the engine.

Player observed_frames is the denominator for all position/occupancy features. Each neighbour
distance and density aggregate has its own valid-frame count. expected_frames is provided only
from explicit roster eligibility: metadata playing_time.by_period intervals contain all 300 selected
frames for each of the 22 participants. visible_fraction=observed_frames/expected_frames measures
usable positional visibility, not confidence. Unknown eligibility leaves that fraction NULL.

Width=max(y)-min(y), depth=max(x)-min(x), including goalkeepers, only with at least 3 valid
visible team players. These are **observed-subset extents**, not inferred full-team dimensions.
Team windows expose separate valid width/depth counts and valid_team_frames. Their
mean_visible_team_players averages available frames (including zero-visible team rows);
wholly absent source frames do not become zero-player frames. frame_coverage_fraction measures
input-frame availability; visible_fraction measures sampling slots with at least one valid visible
team player. Neither means all 11 players were seen. Source rows absent for an entire frame
cannot be reconstructed from player records; expected grid counts still expose that gap.

## Verification

Run `.venv/bin/python -m pytest -q` for the existing suite and focused spatial/adapter/report tests.
Exact fixture: A1=(50,34), A2=(53,38), A3=(40,10), B1=(55,34), B2=(70,50).
A1 nearest teammate=5m; nearest opponent=5m; teammate/opponent counts at 5m and 10m each=1.
A2 nearest opponent=sqrt(20)m; A3 nearest teammate=26m. Team A width=28m and depth=13m;
Team B width=16m and depth=15m when explicitly lowering minimum players to 2 for that fixture.
Paired mirrored scenes preserve team-relative coordinates, zones, distances and extents.
Tests also cover missing coordinates/opponents, duplicates, nonfinite/out-of-pitch values,
empty input, anonymous tracks, one-player teams, partial visibility, window gaps and support counts.
Sanity-guard tests deliberately inject negative distances, oversized extents, nonfinite means,
invalid occupancy sums and coverage >1 and verify rejection.
Final suite results and protected-file hash checks are recorded in verification.json.

## Reproduce without committing raw data

From repository root (network access needed only for these three pinned downloads):

```bash
mkdir -p data/raw/spatial_skillcorner
curl -L --fail --range 0-1048575 'https://media.githubusercontent.com/media/SkillCorner/opendata/4340d274572876239c154c90bc507a9b3250a656/data/matches/1886347/1886347_tracking_extrapolated.jsonl' -o data/raw/spatial_skillcorner/tracking_prefix.jsonl
curl -L --fail 'https://raw.githubusercontent.com/SkillCorner/opendata/4340d274572876239c154c90bc507a9b3250a656/data/matches/1886347/1886347_match.json' -o data/raw/spatial_skillcorner/1886347_match.json
curl -L --fail 'https://raw.githubusercontent.com/SkillCorner/opendata/4340d274572876239c154c90bc507a9b3250a656/LICENSE' -o data/raw/spatial_skillcorner/LICENSE
.venv/bin/python -m src.analysis.spatial_engine_report
```

The report command checks raw SHA256 values before computation; hashes and URLs are in
source_manifest.json. data/raw is already git-ignored. No new dependencies are needed.
CSV content is deterministic for the pinned slice and configuration; runtime metadata varies.
The core entry points are canonical_table, frame_features and window_features in src/spatial.
Player-frame tables are returned by the engine; window CSVs, team-frame CSV and quality CSV
are saved for inspection. Every returned/exported column is covered by feature_dictionary.csv.

## Research limitations and stop condition

- Tracking position ≠ event position; see event_tracking_compatibility.md. Rescaling does not fix sampling bias.
- Future broadcast tracking may have severe visibility and identity bias. This source already demonstrates incomplete observation.
- Width/depth are biased when off-screen players are missing; a small observed extent is not evidence of tactical compactness.
- Nearest visible distance can exceed true nearest distance; observed local density can undercount the true density.
- No possession state, pass, carry, reception, pressure, shot, assist or other event is inferred or used.
- No tactical instruction or coach causality is inferred. No Alonso-specific result is produced.
- Spatial thresholds/zones are explicit project conventions. Confidence is unreported, not perfect.
- One 30-second sample establishes reproducible computation, not match representativeness or provider accuracy.
- No CV, video, model fitting, clustering, formation or between-line inference is implemented.

STOP: deterministic tracking → spatial features only. Next minimum action is review of these
definitions and coverage before selecting a larger rights-cleared tracking validation sample.
