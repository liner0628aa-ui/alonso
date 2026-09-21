# Wirtz — Alonso-Leverkusen Tactical Role MVP

Observed behaviour in StatsBomb Open Data, Bundesliga 2023/24. No causal claim about coaching instructions and no inferred fixed role label.

- Dataset: 34 matches, 137,765 events. Wirtz: 32 appearances, 7,234 player events analysed.
- 360: 31 fixtures with valid UUID joins; 3 excluded for invalid linkage. Downloaded-file availability and orphan counts are recorded in available_data_audit.json.
- Minutes: NULL total; 2,432.03 known minutes; 1 appearances with unknown minutes. Existing lineup/period-end method includes stoppage time. Unknown totals/p90 remain NULL.
- Unknown-minute fixtures: 2023-09-15 vs Bayern Munich (3895074; unknown:temporary_off_pitch).
- Involvement: 5,655 on-ball event proxies, 5,655 with coordinates; 1,850 completed receptions (1,850 located). These are event counts, not distinct physical touches.
- Average on-ball event position: (65.34, 42.60); average reception: (64.49, 42.28) on 0–100 attacking coordinates, y=0 left.
- Spatial shares: left 54.22%, central 14.64%, right 31.14%; half-spaces 43.87% (overlapping the left/right split).
- Final-third involvement: 2,903 located on-ball events (51.34%).
- Passing: 1,841 attempts, 1,543 completed; 879 forward attempts; 198 completed progressive passes.
- Carrying: 1,772 carries; 164 progressive carries.
- Endpoint coverage: 0 passes and 0 carries have unknown endpoints; progression and entry totals count only evaluable actions. Unknown event flags are NULL.
- Entries: 229 into final third, 137 into penalty area, from completed passes and carries crossing the respective boundary.
- Creation/shooting: 61 provider-flagged shot-assist passes; 71 shots, 8.47 StatsBomb xG. Shot coordinates and outcomes are in shot_locations.csv. xA and wider shot-creating chains are not estimated.
- Defensive activity (selected event set): 863 total = 651 pressures + 35 tackles + 16 interceptions + 161 recoveries. Counts do not imply defensive success.

## Interpretation and limits

The figures describe event-weighted on-ball behaviour. They do not measure time spent in zones, off-ball movement, a stable team formation or the whole Alonso system. Reception/carry/pass events can describe the same possession sequence, so the touch proxy overweights longer recorded action chains. All situations, including set pieces, are retained. Progression is the local Δx≥10 definition, not a provider-standard progressive metric. Match variation is unadjusted for opponent, score, minutes and possession. Team context uses all ingested fixtures, including Wirtz absences, and a disclosed 500-event display threshold.

360 is only a verified raw UUID link: advanced spatial features remain NULL and are not used here. Unknown minutes are not replaced by 90 or inferred from event counts. No synthetic events enter any output. See ../../docs/tactical_features_mvp.md and available_data_audit.json for definitions and source coverage.

## Attribution

Data source: StatsBomb Open Data. Research/non-commercial use only; do not redistribute source or processed data. Publications must credit StatsBomb and display its logo. See the StatsBomb Public Data User Agreement (2023-09-08). The agreement asks users to register their interest at the resource centre.

Source: https://github.com/statsbomb/open-data . Local research report; before public publication display the official StatsBomb logo as required. No public distribution was performed.
