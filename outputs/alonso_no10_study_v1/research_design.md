# Alonso No.10 Study v1 — Step 1 research design and feasibility audit

## Research question and hypotheses

**Question:** Do players assigned a No.10 role under Xabi Alonso show a repeated tactical behaviour pattern across Leverkusen, Real Madrid and Chelsea?

- **H1:** Alonso AMs share some tactical behaviour across clubs.
- **H2:** The shared pattern is more internally consistent among Alonso AMs than among comparable non-Alonso AMs.
- **H3:** The role is better represented as a mix of positioning, reception, progression, creation and box involvement than as one position label.

This is a testable hypothesis. A strong cross-club signature, partial signature, club-dependent pattern, or no distinction from non-Alonso peers are all valid outcomes.

## What “No.10” means for this study

The inclusion rule keeps three components separate and is not finalized in Step 1:

**A. Nominal position.** Use the lineup/source position and starting role as context. An attacking-midfield label is evidence for candidacy, never sufficient by itself.

**B. Observed behaviour.** Use only measures present in the current Leverkusen pipeline: on-ball location (`avg_touch_x`, `avg_touch_y`, `halfspace_share`), passing and progression, final-third and box entries, shot assists, xG, and defensive/transition event rates. The current 15 features do not directly measure between-lines reception, off-ball location, defender distance, or line-breaking receptions. They therefore cannot support claims about those behaviours.

**C. Match role context.** Record formation, starting role, home/away and available minutes. The current data provide lineup context, but an explicit in-match role-change series is not implemented; role changes are UNKNOWN unless a future source supplies them.

The future player-match inclusion rule should require repeated evidence across A, B and C, with thresholds pre-registered after the external data schema is known. “No.10” therefore means a player-match repeatedly linking, progressing or creating between midfield and the front line under a documented context, not a single position string.

## Exact existing feature basis

The 15 features and definitions were read from `src/analysis/team_role_space.py` and are reproduced in `feature_compatibility.csv`. They are the generic M2/M3 feature set, not a completed No.10 classifier. `no10_feature_candidates.csv` separates `EXISTING_GENERIC_15`, the currently empty `CROSS_CLUB_CORE`, and `IDEAL_NO10_FEATURES`.

## Candidate scope audit

The local Leverkusen role-vector output verifies Wirtz (29 eligible rows; 2,377.95 represented minutes) and Hofmann (27 eligible rows; 2,250.98 represented minutes) as candidates. Their labels include attacking-midfield and adjacent roles, while their behaviour is only a candidate signal until the rule above is applied. Bellingham, Güler and Palmer have no verified Alonso-match rows in this repository. See `player_scope_candidates.csv`; no candidate is finalized here.

## Data source evidence and licensing

The Hudl/StatsBomb release describes all 34 unbeaten 2023/24 Leverkusen Bundesliga matches, event data and StatsBomb 360, with access through competition 9 and season 281: [release](https://www.hudl.com/blog/free-data-bayer-leverkusens-invincible-bundesliga) (accessed 2026-09-22). The open-data README says selected leagues are made freely available for research and documents events, lineups and selected 360 data, with attribution requirements: [README](https://github.com/hudl/open-data/blob/master/README.md) (accessed 2026-09-22).

Real Madrid's official announcement states that Alonso's term began 1 June 2025: [official announcement](https://www.realmadrid.com/en-US/news/club/announcements/comunicado-oficial-xabi-alonso-25-05-2025) (accessed 2026-09-22). No approved free/legal Real Madrid event, lineup, coordinate or minutes source for that period was found in the repository or this audit. Chelsea's Alonso period is only reported by the secondary AP source reviewed here: [AP report](https://apnews.com/article/7ccc0abd9caa7e4cd0c0bd887b22fc716) (accessed 2026-09-22); official club confirmation and study data remain UNKNOWN. These sources do not establish cross-club data availability.

## Comparison and control design

The preferred control is **Control A** within each club: pre/post-Alonso attacking midfielders in a similar role, with comparable lineup context and minutes. It requires verified seasons before and during Alonso, consistent event definitions, role labels, formations and sufficient minutes. If that is infeasible, use **Control B**: same league and season matched attacking midfielders, matched on minutes, role/context, team possession and opponent/team strength; age is descriptive context, not a matching claim.

The future pipeline is RAW features → train/reference standardization → PCA → cosine/Euclidean similarity → neural representation last. RAW, PCA and NEURAL must all be compared. The prior project finding that PCA beat the neural encoder on neighbour preservation is a reason to keep the neural model as a baseline, not a default winner.

External generalization is valid only for features marked EXACT in every club. Leverkusen-Alonso can be a reference/train set and Real Madrid-Alonso/Chelsea-Alonso genuine external tests only after those exact-compatible data are verified. Approximate features must remain sensitivity analyses and cannot be substituted into the primary test.

## Confounders and limitations

Name and document player ability/style, squad composition, league, opponent, score state, formation, home/away, team possession, sample size and season timing. Current evidence is one club and one season with 34 matches, 376 eligible player-match vectors and 18 players. The external club datasets and licensing are not verified; reception, off-ball and tracking context are incomplete; position is not role; and observed associations do not establish Alonso instruction or causality.

## Gate condition

The audit finds no verified exact feature available for all three clubs. Dataset construction should wait for legal, schema-compatible Real Madrid and Chelsea match/event/lineup/coordinate/minutes sources and a coach-period confirmation for Chelsea.
