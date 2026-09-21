# Alonso-Leverkusen Team Tactical Role Space — Milestone 2

## Dataset and selection

StatsBomb Bundesliga 2023/24: 34 matches, 137,765 events. Leverkusen: 29 lineup players, 680 preserved player-match rows; 516 observed appearances. Analysis: 376 complete player-match vectors, 18 players, 33,081.23 represented minutes. Match minimum 30 known minutes, player season minimum 450 known minutes. 18 players satisfy the season threshold before match/completeness filters. Exclusion reasons (overlapping): {'unknown_minutes': 178, 'season_minutes_below_threshold': 130, 'no_player_events': 167, 'missing_features': 186, 'short_appearance': 120}. Unused lineup members are retained, not counted as appearances. Goalkeepers remain included and may form a distinct region; these core event features are not a dedicated goalkeeper evaluation.

## Feature representation

15 features: avg_touch_x, avg_touch_y, halfspace_share, passes_p90, forward_pass_rate, progressive_passes_p90, progressive_carries_p90, final_third_entries_p90, penalty_area_entries_p90, shot_assists_p90, xg_p90, pressures_p90, recoveries_p90, tackles_p90, interceptions_p90.

Reuse Milestone 1 definitions. Additional count p90 = raw *90 / known minutes. NULL never becomes zero. xA/dangerous passes/360 context are not implemented. Raw metrics and all short/unknown-minute rows remain in Parquet. Identity/lineup columns are context only. Receptions, carries, shots and touch-proxy counts remain descriptive rather than adding correlated involvement/attacking dimensions. Other lane shares, average reception positions, final-third share and defensive-action sum are likewise excluded from the vector to avoid algebraic or near duplication.

StandardScaler fits ONLY eligible player-match rows (unweighted, mean removal and population standard deviation). Each selected feature has equal standardized weight. Season centroid is the match-minute-weighted mean of standardized match vectors using that SAME scaler; no season refit. Rate means equal summed eligible raw counts *90 / summed eligible minutes. Spatial/ratio means are match-minute-weighted, not pooled event-weighted; this is an intentional representation of typical playing time. Median/std are unweighted match summaries (population std). Full-season known minutes include short matches, but represented minutes and metrics only use eligible matches. Unknown-minute appearances are not silently incorporated in rates.

## PCA

PC1: 24.46%; PC2: 20.75%; combined: 45.21%. Full SVD PCA is fitted on eligible standardized match rows; player centroids are projected through the same PCA. Coefficients are unit eigenvector weights, not causal effects; feature-PC correlations are separately exported. Axis signs are arbitrary. No semantic axis names are assigned.

PC1 strongest absolute coefficients: forward_pass_rate (+0.447), progressive_passes_p90 (+0.415), avg_touch_x (-0.409), penalty_area_entries_p90 (-0.337), pressures_p90 (-0.292).

PC2 strongest absolute coefficients: final_third_entries_p90 (+0.466), passes_p90 (+0.446), progressive_carries_p90 (+0.368), recoveries_p90 (+0.322), progressive_passes_p90 (+0.271).

## Core player observations

Player-specific minute-weighted original-unit feature profiles, median/std and lineup context are exported. The following positions are PC coordinates, not named roles:

- Adam Hložek: PC1 -1.528, PC2 -1.568, 5 matches, 368.04 represented minutes; nominal positions: Left Attacking Midfield | Right Attacking Midfield.
- Alejandro Grimaldo García: PC1 -1.068, PC2 +0.147, 30 matches, 2868.14 represented minutes; nominal positions: Left Wing Back.
- Amine Adli: PC1 -2.085, PC2 -0.247, 13 matches, 810.53 represented minutes; nominal positions: Center Forward | Left Attacking Midfield | Left Back | Left Center Forward | Left Wing | Right Attacking Midfield.
- Edmond Fayçal Tapsoba: PC1 +2.431, PC2 +1.071, 23 matches, 2201.54 represented minutes; nominal positions: Left Center Back | Right Center Back.
- Exequiel Alejandro Palacios: PC1 +0.785, PC2 +1.249, 21 matches, 1835.49 represented minutes; nominal positions: Left Defensive Midfield | Right Defensive Midfield.
- Florian Wirtz: PC1 -1.483, PC2 +1.499, 29 matches, 2377.95 represented minutes; nominal positions: Center Attacking Midfield | Center Forward | Left Attacking Midfield | Left Wing | Right Attacking Midfield | Right Wing.
- Granit Xhaka: PC1 +1.460, PC2 +1.815, 29 matches, 2743.61 represented minutes; nominal positions: Left Defensive Midfield | Right Defensive Midfield.
- Jeremie Frimpong: PC1 -2.382, PC2 +0.086, 26 matches, 2197.19 represented minutes; nominal positions: Right Attacking Midfield | Right Wing | Right Wing Back.
- Jonas Hofmann: PC1 -1.905, PC2 +0.159, 27 matches, 2250.98 represented minutes; nominal positions: Center Forward | Left Attacking Midfield | Right Attacking Midfield | Right Center Back | Right Wing.
- Jonathan Tah: PC1 +1.899, PC2 -0.568, 30 matches, 2824.98 represented minutes; nominal positions: Center Back.
- Josip Stanišić: PC1 +0.163, PC2 +0.648, 14 matches, 1301.81 represented minutes; nominal positions: Right Center Back | Right Wing Back.
- Lukáš Hrádecký: PC1 +2.487, PC2 -3.234, 33 matches, 3215.18 represented minutes; nominal positions: Goalkeeper.
- Nathan Tella: PC1 -2.427, PC2 -0.834, 9 matches, 668.09 represented minutes; nominal positions: Left Wing | Right Attacking Midfield | Right Wing | Right Wing Back.
- Odilon Kossonou: PC1 +0.969, PC2 +0.506, 20 matches, 1857.04 represented minutes; nominal positions: Right Center Back.
- Patrik Schick: PC1 -1.902, PC2 -1.892, 13 matches, 955.99 represented minutes; nominal positions: Center Forward | Right Attacking Midfield.
- Piero Martín Hincapié Reyna: PC1 +1.238, PC2 +0.461, 18 matches, 1517.23 represented minutes; nominal positions: Center Back | Left Center Back | Left Wing Back.
- Robert Andrich: PC1 +0.751, PC2 +0.160, 18 matches, 1691.91 represented minutes; nominal positions: Center Back | Left Defensive Midfield | Right Defensive Midfield.
- Victor Okoh Boniface: PC1 -2.014, PC2 -1.269, 18 matches, 1395.54 represented minutes; nominal positions: Center Forward | Left Wing.

## Wirtz nearest observed roles

- Amine Adli: cosine 0.5942, 13 eligible matches.
- Jonas Hofmann: cosine 0.5741, 27 eligible matches.
- Jeremie Frimpong: cosine 0.3565, 26 eligible matches.
- Alejandro Grimaldo García: cosine 0.3139, 30 eligible matches.
- Victor Okoh Boniface: cosine 0.1763, 18 eligible matches.

Cosine uses the full 15-dimensional standardized season vectors, not the 2D plot. This measures similarity in observed tactical behaviour relative to the team-match reference mean, NOT player ability, recruitment fit or a Wirtz role prototype. Negative values are permitted; no 0–100 score. Near-zero vector norms would yield NULL.

## Role stability and variability

Highest mean match-to-own-season-centroid cosine: Lukáš Hrádecký (0.968; n=33); Patrik Schick (0.817; n=13); Jeremie Frimpong (0.799; n=26).

Lowest mean cosine: Robert Andrich (0.432; n=18); Piero Martín Hincapié Reyna (0.597; n=18); Odilon Kossonou (0.600; n=20).

Largest RMS distance from own centroid in standardized feature space: Amine Adli (3.809; n=13); Florian Wirtz (3.274; n=29); Piero Martín Hincapié Reyna (3.242; n=18).

Cosine distributions (mean, median, std, p10, p90) and RMS distances are exported. Angular instability and absolute feature variability are different quantities. Own-centroid cosine is descriptive/in-sample and includes each match in its centroid; leave-one-match-out cosine is additionally exported to expose that optimism. No universal high/low stability cutoff is imposed. A centroid near the population mean can have low cosine even without large absolute movement.

## Limitations and diagnostics

One team and season; no causal claims about Alonso instructions. Events measure on-ball activity, not off-ball position or time occupation. Touch proxies can double-count a single possession sequence. All play patterns, including set pieces, remain. Progression uses the local normalized delta-x>=10 rule. Minutes include added time; temporary off-pitch ambiguities remain NULL. Results depend on thresholds, feature selection, scaling and goalkeeper inclusion. Common opponent/game states, home/away and team possession are not adjusted. Match rows are correlated; no held-out predictive evaluation or uncertainty confidence intervals are claimed. StandardScaler preserves sparse-event outliers: max absolute z=7.02 (xg_p90); feature_correlations.csv exposes residual correlations. No automatic outlier clipping, imputation or tuning to desired neighbours. PCA2 loses 54.79% of variance; use full-space cosine for comparisons. Stability estimates depend on sample count and ignore rotation in time. 360 availability does not enter the vector.

## Attribution

Data source: StatsBomb Open Data. Research/non-commercial use only; do not redistribute source or processed data. Publications must credit StatsBomb and display its logo. See the StatsBomb Public Data User Agreement (2023-09-08). The agreement asks users to register their interest at the resource centre.

Local research outputs only; retain StatsBomb attribution and display its official logo before public publication. No data redistribution performed. Milestone 2 stops here.
