# Alonso Tactical Role Encoder v1

A baseline neural representation of observed 2023/24 Bayer Leverkusen player-match tactical behaviour in a low-dimensional embedding. Interpretation: **observed average tactical role in the 2023/24 Alonso system**. This document is rendered from saved `metrics.json`; CSVs and figures use the same run artifacts.

## Dataset size

| Player-match rows | Matches | Players | Features |
| --- | --- | --- | --- |
| 376 | 34 | 18 | 15 |

M2 eligibility and feature semantics are reused unchanged. Inputs are original feature values, not M2 all-row z scores or PCA coordinates. Only existing local real data is used. Every selected input is finite. Source SHA-256: `22314a89eae69fb39c9c99d0a49550c877ee84f0d34b9dafd31c35da26f67726`.

## Train/validation/test matches

| Split | Matches | Rows | Match IDs |
| --- | --- | --- | --- |
| train | 24 | 269 | statsbomb:match:3895052, statsbomb:match:3895074, statsbomb:match:3895095, statsbomb:match:3895107, statsbomb:match:3895113, statsbomb:match:3895134, statsbomb:match:3895139, statsbomb:match:3895158, statsbomb:match:3895182, statsbomb:match:3895194, statsbomb:match:3895202, statsbomb:match:3895210, statsbomb:match:3895220, statsbomb:match:3895232, statsbomb:match:3895250, statsbomb:match:3895258, statsbomb:match:3895266, statsbomb:match:3895275, statsbomb:match:3895286, statsbomb:match:3895292, statsbomb:match:3895302, statsbomb:match:3895309, statsbomb:match:3895320, statsbomb:match:3895348 |
| val | 5 | 53 | statsbomb:match:3895067, statsbomb:match:3895153, statsbomb:match:3895180, statsbomb:match:3895244, statsbomb:match:3895340 |
| test | 5 | 54 | statsbomb:match:3895060, statsbomb:match:3895086, statsbomb:match:3895121, statsbomb:match:3895167, statsbomb:match:3895333 |

Sorted match IDs are permuted by the split seed and assigned to disjoint groups. StandardScaler and PCA are fitted on training rows only. Validation selects the checkpoint; test rows are first evaluated after selection. Train/validation rows are in-sample for encoder development: training fits weights and validation selects the epoch. The all-row descriptive exports include all three splits; they are not held-out evidence.

## Input features

| Order | Feature | Unit | M2 definition |
| --- | --- | --- | --- |
| 1 | avg_touch_x | 0–100 | Mean located on-ball proxy x; event-weighted, attacking direction |
| 2 | avg_touch_y | 0–100 | Mean located on-ball proxy y; 0 = attacking left |
| 3 | halfspace_share | share | Located proxy events with 20<=y<40 or 60<=y<80 / all located proxy events |
| 4 | passes_p90 | count/90min | All PASS attempts *90 / known match minutes |
| 5 | forward_pass_rate | share | Forward PASS attempts / all PASS attempts; NULL if missing endpoints or no passes |
| 6 | progressive_passes_p90 | count/90min | Completed PASS with normalized delta-x>=10 *90 / minutes |
| 7 | progressive_carries_p90 | count/90min | CARRY with normalized delta-x>=10 *90 / minutes |
| 8 | final_third_entries_p90 | count/90min | Completed PASS or CARRY crossing from x<200/3 to x>=200/3 *90 / minutes |
| 9 | penalty_area_entries_p90 | count/90min | Completed PASS or CARRY entering existing proportional box *90 / minutes |
| 10 | shot_assists_p90 | count/90min | Raw StatsBomb pass.shot_assist=true count *90 / minutes |
| 11 | xg_p90 | xG/90min | Sum raw StatsBomb shot.statsbomb_xg *90 / minutes |
| 12 | pressures_p90 | count/90min | PRESSURE events *90 / minutes, not successful pressures |
| 13 | recoveries_p90 | count/90min | RECOVERY events *90 / minutes, not success rate |
| 14 | tackles_p90 | count/90min | Duel subtype Tackle events *90 / minutes |
| 15 | interceptions_p90 | count/90min | INTERCEPTION events *90 / minutes |

Identity, player name, match ID, position, formation, minutes and all other context are excluded from model input. Feature order is serialized and enforced at inference.

## Architecture and fixed defaults

```json
{
  "architecture": [
    15,
    12,
    8,
    4,
    8,
    12,
    15
  ],
  "activation": "GELU",
  "bottleneck_activation": "linear",
  "output_activation": "linear",
  "latent_dim": 4,
  "loss": "MSE",
  "optimizer": "Adam",
  "lr": 0.001,
  "weight_decay": 1e-05,
  "batch_size": 32,
  "max_epochs": 500,
  "patience": 40,
  "min_delta": 0.0,
  "device": "cpu",
  "threads": 1
}
```

The bottleneck is linear; GELU follows each hidden layer except the bottleneck and final output. Python, NumPy and torch are seeded. CPU execution uses deterministic algorithms and one torch thread. No hyperparameter search or test-guided model changes. Each robustness run changes both match partition and model/batch random seed.

```json
{
  "split_method": "seeded permutation of sorted match IDs; 24/5/5 matches",
  "same_player_cohesion": "unordered Euclidean pairs among players with >=2 test rows in both pair sets",
  "variance": "population variance",
  "across_split_std": "sample standard deviation (ddof=1)",
  "verdict": ">=8 joint wins AND paired mean improvement > paired across-split sample std for BOTH primary metrics",
  "latent_activation": "linear",
  "seeds": "42..51 used for split, initialization and batch order",
  "extra_dependencies": "pytest is a validation tool; torch is the only new direct runtime dependency"
}
```

## Best epoch

| Saved seed | Best epoch | Epochs run | Scaler fit rows | PCA fit rows |
| --- | --- | --- | --- | --- |
| 42 | 165 | 205 | 269 | 269 |

The minimum validation-loss state_dict was restored before final evaluation. Full epoch histories for every run are saved in `training_history.csv`.

## Train/validation/test reconstruction MSE

| Split | Autoencoder | PCA | Training-mean reference |
| --- | --- | --- | --- |
| train | 0.389607 | 0.388004 | 1.000000 |
| val | 0.456593 | 0.474030 | 1.111155 |
| test | 0.427661 | 0.484836 | 1.117129 |

All errors use the same train-standardized feature units, with equal weight for each feature and each row. The reference predicts the training feature mean.

| Test feature | Autoencoder MSE | PCA MSE | Mean reference MSE |
| --- | --- | --- | --- |
| avg_touch_x | 0.155805 | 0.186958 | 1.026506 |
| avg_touch_y | 0.694120 | 0.358394 | 0.989458 |
| halfspace_share | 0.486041 | 0.613265 | 0.974469 |
| passes_p90 | 0.283027 | 0.181426 | 0.976782 |
| forward_pass_rate | 0.218668 | 0.197480 | 1.046099 |
| progressive_passes_p90 | 0.172283 | 0.126369 | 0.813665 |
| progressive_carries_p90 | 0.587996 | 0.684991 | 1.524285 |
| final_third_entries_p90 | 0.179422 | 0.173294 | 0.849382 |
| penalty_area_entries_p90 | 0.266146 | 0.285521 | 1.063417 |
| shot_assists_p90 | 0.191207 | 0.407181 | 1.024954 |
| xg_p90 | 0.453070 | 1.805883 | 2.641413 |
| pressures_p90 | 0.648675 | 0.506611 | 0.891213 |
| recoveries_p90 | 0.372169 | 0.516455 | 0.845077 |
| tackles_p90 | 1.104016 | 0.754001 | 1.402547 |
| interceptions_p90 | 0.602276 | 0.474713 | 0.687675 |

## PCA baseline

The comparison uses sklearn PCA with four components and full SVD, refitted independently inside each training split. The M2 all-row PCA is not used for evaluation. Its existing loadings were inspected during preflight. The optional two-dimensional projection of neural embeddings is an all-row visualization only.

## Neighbour preservation

| Test rows | Autoencoder overlap | PCA overlap | Chance k/(n−1) |
| --- | --- | --- | --- |
| 54 | 0.537037 | 0.618519 | 0.094340 |

For each test row, compare its five nearest other test rows in standardized feature space with its five nearest other test rows in the corresponding embedding. Distances are Euclidean, self-neighbours excluded, overlap is intersection size divided by five. Ties use stable input order. Chance is the expected overlap for independent uniformly random neighbour sets, not a hypothesis-test p-value.

## Same-player cohesion

| Representation | Within/between distance ratio | Same-player pairs | Different-player pairs | Eligible players |
| --- | --- | --- | --- | --- |
| ae | 0.481811 | 82 | 1046 | 11 |
| pca | 0.494581 | 82 | 1046 | 11 |
| raw | 0.647135 | 82 | 1046 | 11 |

Lower ratios indicate closer same-player observations relative to different-player observations. Only players with at least two test rows enter either pair set; unordered pairs receive equal weight. This measure is confounded with position and is descriptive only. It is not part of the superiority verdict.

## Latent variance and collapse diagnostics

| Dimension | AE train variance | AE test variance | AE all-row variance | PCA test variance |
| --- | --- | --- | --- | --- |
| z1 | 3.151622 | 5.151288 | 3.695749 | 3.809462 |
| z2 | 2.900588 | 3.991871 | 3.228007 | 3.214430 |
| z3 | 5.159983 | 6.098312 | 5.330414 | 1.605089 |
| z4 | 5.453456 | 5.897986 | 5.648781 | 0.840600 |

Collapse flag uses absolute population variance ≤ 0.000001. Seed-42 test collapsed AE dimensions: []; PCA: []. This flags near-constant coordinates, not every form of redundant latent information.

## 10-split robustness and pre-registered verdict

| Seed | Train/val/test rows | Best epoch | AE MSE | PCA MSE | AE overlap | PCA overlap | AE cohesion | PCA cohesion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | 269/53/54 | 165 | 0.427661 | 0.484836 | 0.537037 | 0.618519 | 0.481811 | 0.494581 |
| 43 | 268/53/55 | 161 | 0.493481 | 0.420141 | 0.461818 | 0.556364 | 0.537964 | 0.619014 |
| 44 | 267/53/56 | 244 | 0.409655 | 0.428830 | 0.471429 | 0.567857 | 0.527651 | 0.478528 |
| 45 | 265/56/55 | 377 | 0.415895 | 0.450572 | 0.483636 | 0.556364 | 0.477040 | 0.541265 |
| 46 | 263/56/57 | 272 | 0.344708 | 0.429128 | 0.487719 | 0.575439 | 0.586636 | 0.527038 |
| 47 | 266/55/55 | 500 | 0.346331 | 0.358423 | 0.538182 | 0.585455 | 0.412234 | 0.433624 |
| 48 | 265/56/55 | 382 | 0.435874 | 0.415619 | 0.523636 | 0.541818 | 0.558099 | 0.591891 |
| 49 | 266/53/57 | 337 | 0.312339 | 0.312646 | 0.501754 | 0.600000 | 0.466753 | 0.585909 |
| 50 | 266/56/54 | 500 | 0.287916 | 0.296906 | 0.607407 | 0.625926 | 0.465286 | 0.471174 |
| 51 | 263/58/55 | 494 | 0.415907 | 0.448676 | 0.461818 | 0.610909 | 0.604347 | 0.514498 |

| Metric | AE mean ± std | PCA mean ± std | AE wins | Mean improvement | Std of improvement |
| --- | --- | --- | --- | --- | --- |
| mse | 0.388977 ± 0.063560 | 0.404578 ± 0.061673 | 8 | 0.015601 | 0.042975 |
| neighbour_overlap | 0.507444 ± 0.045368 | 0.583865 ± 0.029006 | 0 | -0.076421 | 0.039787 |
| cohesion | 0.511782 ± 0.060972 | 0.525752 ± 0.059375 | 7 | 0.013970 | 0.065638 |

Across-run standard deviations are sample standard deviations. Positive paired improvement means PCA−AE for MSE/cohesion and AE−PCA for overlap. The mean reference MSE is 0.980951 ± 0.127676; raw-space cohesion is 0.666037 ± 0.037277.

Pre-registered rule: at least eight of ten splits must have BOTH lower AE test MSE and higher AE neighbour overlap; for EACH of those two metrics the mean paired improvement must also exceed its across-split sample standard deviation. Joint wins: **0/10**. The split sets overlap and are not independent replications; error bars are not confidence intervals. Metrics are computed within each run. Latent vectors from different models are never pooled.

**At this dataset size the autoencoder is comparable to or worse than the PCA baseline.**

The AE has lower reconstruction MSE in 8 of 10 splits, but higher neighbour overlap in 0. Reconstruction improvement therefore does not establish a better role-neighbour geometry. In the saved run the largest per-feature reconstruction reduction is for `xg_p90` (PCA 1.805883, AE 0.453070). The categorical fallback “comparable” denotes failure to establish the pre-registered superiority claim; it is not a statistical equivalence finding.

## Player embedding observations

| Player | Matches | Minutes | z1 mean | z2 mean | z3 mean | z4 mean | RMS spread | Low confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Adam Hložek | 5 | 368.039400 | -2.933675 | -0.230537 | 2.324003 | -1.926173 | 2.010603 | False |
| Alejandro Grimaldo García | 30 | 2868.139633 | -1.810935 | -0.603510 | -0.438366 | -1.262931 | 2.197301 | False |
| Amine Adli | 13 | 810.533633 | -3.056043 | -1.036506 | -0.200981 | -2.391532 | 4.070103 | False |
| Edmond Fayçal Tapsoba | 23 | 2201.535800 | -0.821930 | -0.949983 | 0.778169 | 2.014092 | 1.945910 | False |
| Exequiel Alejandro Palacios | 21 | 1835.489533 | -0.935523 | -0.749495 | -0.339955 | 0.006519 | 1.799179 | False |
| Florian Wirtz | 29 | 2377.950950 | -3.375162 | -2.793489 | -0.743939 | -1.227562 | 2.888993 | False |
| Granit Xhaka | 29 | 2743.606917 | -1.193335 | -1.592036 | -0.485086 | 0.715821 | 1.969826 | False |
| Jeremie Frimpong | 26 | 2197.185467 | -5.246000 | -2.521070 | -0.274238 | -3.782168 | 2.327491 | False |
| Jonas Hofmann | 27 | 2250.981267 | -3.401693 | -1.335910 | -0.788503 | -2.915767 | 3.473246 | False |
| Jonathan Tah | 30 | 2824.975583 | -0.695420 | 0.375182 | 2.001780 | 1.985748 | 1.524291 | False |
| Josip Stanišić | 14 | 1301.806650 | -1.799378 | -1.252320 | 0.149417 | -0.061114 | 2.174602 | False |
| Lukáš Hrádecký | 33 | 3215.179200 | -1.991986 | 2.183085 | 5.954740 | 3.174183 | 0.430775 | False |
| Nathan Tella | 9 | 668.091067 | -3.979363 | -0.556876 | 0.463290 | -4.230066 | 1.933908 | False |
| Odilon Kossonou | 20 | 1857.043200 | -1.246361 | -1.028868 | 0.519701 | 0.912233 | 2.292014 | False |
| Patrik Schick | 13 | 955.991783 | -3.960469 | -0.333731 | 3.044249 | -2.948025 | 2.292253 | False |
| Piero Martín Hincapié Reyna | 18 | 1517.227967 | -0.761848 | -0.351172 | 0.339882 | 0.457286 | 1.860414 | False |
| Robert Andrich | 18 | 1691.908600 | -0.912358 | -0.223938 | 0.595022 | 0.504096 | 2.322967 | False |
| Victor Okoh Boniface | 18 | 1395.544333 | -5.614954 | -2.175949 | 3.428740 | -2.961586 | 3.425818 | False |

Season means, medians and population standard deviations use equal weight for each eligible match. Minutes and match counts are context. Players with fewer than five eligible matches are flagged low-confidence. These are descriptions of the observed sample; no dimensions are named as tactical roles.

The smallest within-player RMS spread is Lukáš Hrádecký (0.430775); the largest is Amine Adli (4.070103). These values describe variation under this encoder and do not measure consistency of player quality. The compact goalkeeper observations visible in the plots also illustrate the influence of including that distinct position in training.

## Wirtz observations

| Matches | Minutes | RMS spread | z1 std | z2 std | z3 std | z4 std |
| --- | --- | --- | --- | --- | --- | --- |
| 29 | 2377.950950 | 2.888993 | 1.564936 | 1.527888 | 1.536591 | 1.096222 |

| Nearest player by cosine | Matches | Cosine | Euclidean distance | Euclidean rank |
| --- | --- | --- | --- | --- |
| Jeremie Frimpong | 26 | 0.790085 | 3.212613 | 6 |
| Jonas Hofmann | 27 | 0.748632 | 2.230977 | 2 |
| Amine Adli | 13 | 0.682972 | 2.199649 | 1 |
| Josip Stanišić | 14 | 0.462199 | 2.648959 | 3 |
| Nathan Tella | 9 | 0.429878 | 3.979941 | 9 |

| Prototype excluding Wirtz | Rows | Players | Cosine | Euclidean distance |
| --- | --- | --- | --- | --- |
| wing_back | 65 | 5 | 0.751142 | 1.999507 |
| attacking_midfielder | 38 | 6 | 0.586202 | 2.546241 |
| striker | 32 | 4 | 0.236731 | 4.484133 |
| central_midfielder | 64 | 3 | 0.061724 | 3.380363 |
| centre_back | 104 | 7 | -0.492037 | 4.431753 |

All Wirtz rows are removed before recomputing prototype centroids and minimum group eligibility. The same training latent mean centres both comparison vectors. Wirtz still belongs to the training reference where his rows were assigned to train; this is a descriptive exclusion from prototypes, not leave-one-player-out model evaluation. The CSV contains typed season_mean, neighbour_player, player_match (with split) and prototype_without_wirtz records. These similarities describe observed tactical behaviour, not a quality comparison.

The nearest season centroid by centred cosine is Jeremie Frimpong (cosine 0.790085, Euclidean rank 6), while the nearest by Euclidean distance is Amine Adli. The ranking depends on the chosen geometry. The nearest eligible prototype after excluding Wirtz is `wing_back`. This nearest broad-group centroid does not assign Wirtz a position or prove a tactical role.

## Role prototype summary

Position metadata comes from M2 `nominal_position`, including substitutes. The inspected position mapping is explicit:

```json
{
  "Goalkeeper": "goalkeeper",
  "Left Center Back": "centre_back",
  "Center Back": "centre_back",
  "Right Center Back": "centre_back",
  "Left Wing Back": "wing_back",
  "Right Wing Back": "wing_back",
  "Left Back": "full_back",
  "Left Defensive Midfield": "central_midfielder",
  "Right Defensive Midfield": "central_midfielder",
  "Left Attacking Midfield": "attacking_midfielder",
  "Right Attacking Midfield": "attacking_midfielder",
  "Center Attacking Midfield": "attacking_midfielder",
  "Left Wing": "winger",
  "Right Wing": "winger",
  "Center Forward": "striker",
  "Left Center Forward": "striker"
}
```

| Built group | Rows | Distinct players |
| --- | --- | --- |
| attacking_midfielder | 61 | 7 |
| central_midfielder | 64 | 3 |
| centre_back | 104 | 7 |
| striker | 33 | 5 |
| wing_back | 65 | 5 |

| Skipped group | Rows | Distinct players | Reason |
| --- | --- | --- | --- |
| full_back | 1 | 1 | fewer than 20 rows; fewer than 2 distinct players |
| goalkeeper | 33 | 1 | fewer than 2 distinct players |
| winger | 15 | 6 | fewer than 20 rows |

A prototype needs at least twenty rows and two distinct players. Its centroid, per-dimension population variance and original-feature means use all eligible rows. General player↔prototype similarity can include the queried player in the prototype; the Wirtz-specific result excludes him. These all-row summaries must not be treated as held-out prototype validation. **Position is not role.**

Skipped groups after Wirtz exclusion:

| Group | Rows | Players | Reason |
| --- | --- | --- | --- |
| full_back | 1 | 1 | fewer than 20 rows; fewer than 2 distinct players |
| goalkeeper | 33 | 1 | fewer than 2 distinct players |
| winger | 10 | 5 | fewer than 20 rows |

## Latent–feature relationships

Pearson and Spearman correlations use all rows. Sensitivity is mean absolute autograd derivative with respect to the train-scaled input feature. The table lists the three strongest features separately for each measure; full values are in CSV.

| Dimension | Top |Pearson| | Top |Spearman| | Top sensitivity |
| --- | --- | --- | --- |
| z1 | xg_p90 (-0.732185); penalty_area_entries_p90 (-0.622638); progressive_passes_p90 (0.501873) | avg_touch_x (-0.650340); progressive_passes_p90 (0.630186); penalty_area_entries_p90 (-0.605233) | xg_p90 (0.458570); penalty_area_entries_p90 (0.340337); passes_p90 (0.320376) |
| z2 | progressive_carries_p90 (-0.692374); penalty_area_entries_p90 (-0.642665); avg_touch_x (-0.636362) | progressive_carries_p90 (-0.672905); penalty_area_entries_p90 (-0.639105); avg_touch_x (-0.585072) | progressive_carries_p90 (0.480765); recoveries_p90 (0.412210); xg_p90 (0.368734) |
| z3 | avg_touch_x (-0.632244); shot_assists_p90 (-0.629133); passes_p90 (-0.597339) | shot_assists_p90 (-0.667643); final_third_entries_p90 (-0.633850); passes_p90 (-0.586878) | tackles_p90 (0.446769); final_third_entries_p90 (0.441606); passes_p90 (0.418481) |
| z4 | forward_pass_rate (0.826409); avg_touch_x (-0.812702); progressive_passes_p90 (0.663786) | avg_touch_x (-0.862940); forward_pass_rate (0.858651); progressive_passes_p90 (0.749709) | forward_pass_rate (0.412036); avg_touch_x (0.366744); shot_assists_p90 (0.347585) |

These associations and sensitivities are descriptive, not causal. Autoencoder latent axes have arbitrary sign/rotation, are not identifiable and are not stable across seeds. Distances and angular relationships also depend on the learned latent geometry; reconstruction alone does not constrain that geometry to preserve neighbours. No semantic names are assigned to axes.

## Inference and artifact verification

Offline `encode_player_match`, `encode_player_dataset` and `compare_to_role_prototypes` are in `src/models/inference.py`. Missing, nonnumeric and non-finite features raise named errors; extra columns are ignored with warnings. Range flags compare raw inputs with the training feature min/max; a flag is descriptive and is not a calibrated out-of-distribution probability. Near-zero centred vectors have undefined cosine (JSON null). Checkpoints reload with `weights_only=True`; inference reads scaler parameters from JSON. `scaler.pkl` is also saved for local reproducibility.

```json
{
  "encoder_reload_max_absolute_error": 0.0,
  "autoencoder_reload_passed": true,
  "reproducibility": {
    "previous_run_available": true,
    "tolerance": 1e-05,
    "previous_test_mse": 0.42766139344253584,
    "current_test_mse": 0.42766139344253584,
    "absolute_difference": 0.0,
    "passed": true
  },
  "full_pytest": {
    "passed": 79,
    "failed": 0,
    "log": ".................................................... [ 65%]\n...........................                                              [100%]\n79 passed, 20 subtests passed in 8.96s"
  },
  "figures": [
    {
      "file": "training_curve.png",
      "sha256": "c1c6667c88ca843ef0d5c46523e4feedc7a96bbafd09eb8b72275e01bb956327",
      "visually_inspected": true
    },
    {
      "file": "embedding_player_map.png",
      "sha256": "7d0f14ed73d059f35efbe172f9ffacb4fb801797be9e822088cedd3ff18c7c37",
      "visually_inspected": true
    },
    {
      "file": "embedding_by_player.png",
      "sha256": "fa26cb0d830f385b43f54c1f8632522e35d5b2226dc3e50a7c04f1e534fbc244",
      "visually_inspected": true
    },
    {
      "file": "neural_similarity_heatmap.png",
      "sha256": "d8442918b585eff25133b595d0d6a159a22083da6c8b03bab27ae3bd6dff9c4b",
      "visually_inspected": true
    },
    {
      "file": "wirtz_embedding_neighbours.png",
      "sha256": "8648eb965206d1d39e340ac5909d57c0b85fc164b62b574680e57c8dfd812eb2",
      "visually_inspected": true
    },
    {
      "file": "autoencoder_vs_pca.png",
      "sha256": "aeced66ac9a702ab6da4ccb7ca4626ca6ede2383756cfc41b0d5ec6eb8ad6b8a",
      "visually_inspected": true
    },
    {
      "file": "latent_feature_relationships.png",
      "sha256": "be8822f8de909a46e0ff52a08804f90ccb0494e522c8d47cfce992d40c7cfe1e",
      "visually_inspected": true
    }
  ],
  "artifact_audit_passed": true,
  "independent_reloaded_test_mse": 0.427661392942784,
  "inference_public_functions_passed": true,
  "m2_source_and_output_hashes_unchanged": true,
  "code_review": "Independent read-only review; Arrow input issue reproduced and fixed; regression test passes."
}
```

Library versions: `{"python": "3.13.5", "torch": "2.14.0+cpu", "numpy": "2.5.3", "scikit-learn": "1.9.1", "scipy": "1.18.1", "pyarrow": "25.0.1", "matplotlib": "3.11.2", "pytest": "9.1.1"}`. Git commit: `None` (Unavailable if git executable or commit metadata is absent.).

## Limitations

34 matches / 376 rows / 18 players is small for a neural network. The seed-42 test set has only 5 matches. Single team, single season, single coach; no external validation. Latent axes are not identifiable. Position is not role. Player-match observations are correlated within players and matches; repeated random splits overlap and do not create more independent data. Players are shared across train/test, so the test measures held-out matches, not unseen-player generalization. The splits are random, not chronological forecasts. The eligibility filter omits short, unknown-minute and incomplete appearances. Events describe on-ball behaviour, not off-ball positioning, instructions or causal effects. Goalkeepers remain included in model training, which can influence reconstruction and geometry. Sparse features and extreme observations can dominate squared error. No confidence intervals, calibrated recruitment/system-fit score, player-quality ranking or external-player predictions are claimed.

## Outputs and attribution

Seven PNGs, metrics.json, full training histories, match/season embeddings, prototype tables, similarity tables and Wirtz records are saved beside this report. Model/scaler/configuration/feature-order/training metadata artifacts are in `models/alonso_tactical_encoder_v1/`. Data: StatsBomb Open Data. Retain the existing M2 attribution and source-use conditions. Milestone 3 stops at this descriptive baseline.
