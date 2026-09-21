# Tactical report definitions — event-mvp-v1

This standalone report consumes the existing validated Parquet snapshot. It does not populate the canonical feature registry with incompatible proxy definitions. IDs and coordinates use the existing adapter. All events are real StatsBomb records; synthetic unit tests never enter the report.

| Metric | Definition |
|---|---|
| Sample | Wirtz ID 40724, Leverkusen ID 904, periods 1–4, ingested Alonso fixtures; appearances with positive known minutes or player events |
| Minutes | Existing lineup position intervals plus Half End elapsed timestamps, including added time, excluding breaks. Unknown remains NULL; aggregate total and p90 NULL if any appearance minutes unknown. Known-minute subtotal disclosed. |
| Touches proxy | PASS, CARRY, SHOT, DRIBBLE and completed RECEIPT events. Not physical touches, unique possessions or provider total touches; multiple records in one on-ball sequence counted separately. Defensive events excluded. |
| Receptions | Canonical RECEIPT outcome COMPLETE (StatsBomb Ball Receipt*). Incomplete receipts excluded. |
| Spatial average/share | Event-weighted starts of located touch proxies/completed receipts. Missing coordinate events excluded only from spatial denominator; count and located count both exported. Empty denominator NULL. |
| Lanes | Reuse pitch_zones: y=[0,20) left wing; [20,40) left half-space; [40,60) centre; [60,80) right half-space; [80,100] right wing. Left = y<40, central = [40,60), right = y≥60. Half-space sum overlaps left/right. Not time occupation. |
| Final-third involvement | Located touch proxy starts x≥200/3; share uses located touch proxies. |
| Passes / forward passes | All PASS attempts; forward if end_x>start_x with both coordinates known (including unsuccessful attempts). Completion from canonical outcome. |
| Progressive passes/carries | Local transparent baseline: normalized end_x−start_x≥10 (12 StatsBomb source x units), completed PASS or any CARRY. No inferred carry outcome. Not StatsBomb/Opta/Wyscout progressive definition and not metres. All play patterns including set pieces retained. |
| Entries | Completed PASS or CARRY starting outside and ending inside the target. Final third x≥200/3. Box uses existing StatsBomb proportional geometry x≥85, 22.5≤y≤77.5. In-zone actions excluded; path crossing cannot be inferred from endpoints. |
| Shots / locations / xG | SHOT events, canonical start coordinates and outcome; official shot.statsbomb_xg summed from receipt-checked raw payload. Not model-generated numbers. |
| Creation | Raw pass.shot_assist=true count. No xA, assist chain or broad shot-creating-action estimate. |
| Defensive actions | PRESSURE + TACKLE (Duel subtype Tackle) + INTERCEPTION + RECOVERY event counts. Selected activity set, not all defence or successful actions; foul types not conflated. |
| p90 | Sum raw count ×90 / total known minutes only when all contributing minutes known; never mean of match p90. |
| Advanced 360 | nearest_defender_distance remains NULL, unimplemented. UUID availability never implies full-event coverage or continuous tracking. |

Report CSV has one row per appearance, pooled totals in a separate CSV. Event flags and shot CSVs allow reconciliation. Team map is event-weighted across all ingested fixtures, not a simultaneous formation; display players with ≥500 located on-ball proxies. Match variation uses raw counts and means, without context adjustment. The report manifest links processed checksums and retains the exact license notice. Local analysis only; attribution and official logo required before publication.

Missing action endpoints: event flags are NULL, never false. Aggregate progression/entry counts represent observed evaluable actions only; passes_unknown_endpoints and carries_unknown_endpoints disclose excluded unknown actions. Non-action flags are false (not applicable).
