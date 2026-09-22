# Event-based position vs tracking-based position

All three comparisons are **RELATED BUT DIFFERENT MEASUREMENT**. None is an exact
replacement for an existing M2 input. No M2/M3 definition, feature order, output,
model, or previous research artifact is changed.

| Existing M2 feature | Actual existing definition | Tracking counterpart | Classification |
|---|---|---|---|
| avg_touch_x | Arithmetic mean normalized_x of located on-ball proxy events in periods 1–4; 0–100 attacking coordinate | tracking_avg_x_m: arithmetic mean team-relative x_m of valid visible/detected tracking frames, on a regular sampling grid | RELATED BUT DIFFERENT MEASUREMENT |
| avg_touch_y | Arithmetic mean normalized_y of the same located proxy events; 0–100 with 0 on attacking left | tracking_avg_y_m: arithmetic mean team-relative y_m of valid visible/detected tracking frames, on a regular sampling grid | RELATED BUT DIFFERENT MEASUREMENT |
| halfspace_share | Located proxy events with 20<=normalized_y<40 or 60<=normalized_y<80 divided by all located proxy events | tracking_halfspace_occupancy: valid frames in [13.6,27.2) or [40.8,54.4) team-relative metres divided by all valid player tracking frames | RELATED BUT DIFFERENT MEASUREMENT |

## Verified existing implementation

- `src/data/sources/statsbomb.py:normalize_event` supplies StatsBomb source extents
  120×80, `direction='left_to_right'`, `y_origin='top'` to the existing normalizer.
  This relies on the event source's attacking-oriented locations, not a fixed
  stadium-frame tracking feed.
- `src/data/coordinate_normalization.py:normalize_point` scales x/120×100 and
  y/80×100 in that call. Its generic opposite-direction path rotates both axes.
- `src/analysis/wirtz_role_mvp.py:touches` selects PASS, CARRY, SHOT, DRIBBLE and
  completed RECEIPT events. Other selected types do not require a completion outcome.
- `located` keeps proxy events with non-NULL normalized_x; ingestion validates
  complete coordinate pairs. `metrics` filters periods 1–4, then calculates the
  means and half-space predicate directly. No located proxies means NULL.
- `src/config/pitch_zones.py` holds the previous project's 20/40/60/80 lateral
  boundaries. Its lane names are left_wing/left_halfspace/centre/right_halfspace/right_wing.
- `src/analysis/team_role_space.py:FEATURE_SPECS` exposes these exact event
  definitions to M2. `src/models/tactical_encoder.py` imports the fixed M2 feature
  contract; no tracking feature is inserted into it.

## Why scaling is insufficient

Multiplying event x by 1.05 and event y by 0.68 expresses their normalized values
on a 105×68 reference pitch, but leaves them **event-weighted on-ball positions**.
It does not recover elapsed time, off-ball positioning or physical touch counts.
A pass/receipt/carry chain can supply several event records; players with many
recorded actions receive more weight at those locations. Long off-ball intervals
can supply no records at all. The event coordinates also use proportional provider
pitch units rather than measured match-specific physical dimensions.

Tracking samples include positions without on-ball actions. At uniform sampling
frequency, the valid-frame average/share represents observed tracking time. Missing
frames remain missing; there is no interpolation or assumption that a position was
held through a gap. This v1 rejects off-grid sampling rather than silently allowing
irregular samples to act as elapsed-time weights. Frame-count coverage accompanies
every aggregate, and neighbour statistics expose their separate support counts.

The five-zone boundaries are proportionally aligned with the previous broad lane
concept; that only aligns the spatial partition. It does not align the denominator.
The zones are the project's explicit v1 convention, not a universal half-space definition.
With explicit attacking direction, y=0 means attacking left in both representations;
an x-only mirror would corrupt lateral comparability and is not used.

## Bias and implications for a later hybrid study

Event samples favour ball involvement. Broadcast tracking favours the camera's
visible region, usually related to the ball and match phase; off-screen movement,
occlusion, identity errors and extrapolation introduce additional selection and
measurement bias. SkillCorner is provider-estimated broadcast tracking, not an
independent ground-truth label for validating those same provider estimates.
The smoke test excludes extrapolated/unknown-visibility rows and records that loss.

Tracking nearest-visible distances can overestimate true nearest distances, while
local counts can underestimate true density. Team width/depth measure the visible
subset and can underestimate full-team extents. Coverage thresholds do not establish
neighbourhood completeness or remove missing-not-at-random bias.

For a future HYBRID StatsBomb/video study, treating these quantities as equal would
confound measurement method with club. Shared units, similar names, standardization,
high correlation or successful geometry tests do not establish equivalence.
Matched-player/time validation could assess positional error and **event-time sampled**
tracking positions, but cannot by itself equate event-weighted and continuous-time
estimands. Use a common measurement process or retain these as separately named
outcomes with explicit source/visibility sensitivity analyses. No claim of hybrid
defensibility, possession, coach instruction, or Alonso-specific effect is made here.
