# Alonso No.10 Study v1 — Step 2: data acquisition route

Audit date: **2026-09-22**. This is a design and source audit, not an acquisition or model experiment. All external sources below were accessed on this date; historical publication dates are stated separately where material.

## Decision and scope

**Primary decision: B — obtain legitimate provider/research access before coding.** First request Hudl StatsBomb raw event and lineup access for the verified Alonso periods at Real Madrid and Chelsea. Ask for an exact match inventory, a small permitted example, schema/version documentation and explicit research/publication permissions. The product exists; target-match availability, eligibility for research access, price and a grant of rights are **UNKNOWN**. This is an acquisition recommendation, not an assertion that a supplier has accepted the project.

**Recommended design: OTHER — one event provider and one verified definition set across all three clubs.** Retain the existing Leverkusen baseline and require field-level equivalence for external data. If another supplier is used, it must support a common definition set for all three clubs, including a newly authorized Leverkusen source comparison; provider-specific xG and event taxonomies cannot be silently substituted. No new data or feature computation is authorized by this report.

The audit did **not** find verified public Real Madrid-Alonso or Chelsea-Alonso event data satisfying the required fields. Step 1 Decision C and the empty EXACT-only three-club intersection remain valid. All three clubs remain mandatory. Source discovery is not exhaustive proof that data do not exist.

B is preferred to C because the present hypothesis needs comparable match/identity/minutes/event measurements, while a video pipeline introduces both footage rights and a different measurement process. A is unsupported. C is a conditional engineering alternative, not selected. D would be appropriate if legitimate provider access and rights-cleared video are both ruled out; neither has been ruled out yet.

## New coach-period evidence; Step 1 remains unchanged

The original Real Madrid appointment gave a contractual start of 2025-06-01. A later official termination announcement dated **2026-01-12** bounds the actual appointment: do not request all of 2025/26 as if Alonso coached it throughout. [Appointment](https://www.realmadrid.com/en-US/news/club/announcements/comunicado-oficial-xabi-alonso-25-05-2025); [termination](https://www.realmadrid.com/es-ES/noticias/club/comunicados/comunicado-oficial-xabi-alonso-12-01-2026).

Chelsea's official site confirms the appointment, and a separate official article specifies the beginning of July before 2026/27. This resolves Step 1's missing official appointment source, without establishing a usable event dataset or any player's availability. Request only completed, independently verified matches after the documented start and by the audit cutoff; exact usable counts remain UNKNOWN. [Chelsea appointment](https://www.chelseafc.com/en/news/article/xabi-alonso-appointed-chelsea-manager); [start-period context](https://www.chelseafc.com/en/news/article/mcfarlane-reacts-to-really-exciting-xabi-alonso-appointment).

Coach-period evidence is not proof of match-level participation, role assignment, or data coverage. Each future match still needs a verified date, competition and coach. Exclude 2025 Club World Cup Chelsea matches from a Chelsea-Alonso request; they precede the verified start. Real Madrid's 2025 tournament coverage, if offered, must be assessed separately from league matches.

## Current repository and immutable measurement contract

Read all six Step 1 files, `src/analysis/team_role_space.py`, `src/analysis/wirtz_role_mvp.py`, and the referenced pitch-zone constants. No pipeline was executed to recompute features. The following is the exact ordered generic vector definition extracted from the code:

| Feature | Implemented definition |
|---|---|
| avg_touch_x | Mean located on-ball proxy x; event-weighted, attacking direction |
| avg_touch_y | Mean located on-ball proxy y; 0 = attacking left |
| halfspace_share | Located proxy events with 20<=y<40 or 60<=y<80 / all located proxy events |
| passes_p90 | All PASS attempts *90 / known match minutes |
| forward_pass_rate | Forward PASS attempts / all PASS attempts; NULL if missing endpoints or no passes |
| progressive_passes_p90 | Completed PASS with normalized delta-x>=10 *90 / minutes |
| progressive_carries_p90 | CARRY with normalized delta-x>=10 *90 / minutes |
| final_third_entries_p90 | Completed PASS or CARRY crossing from x<200/3 to x>=200/3 *90 / minutes |
| penalty_area_entries_p90 | Completed PASS or CARRY entering existing proportional box *90 / minutes |
| shot_assists_p90 | Raw StatsBomb pass.shot_assist=true count *90 / minutes |
| xg_p90 | Sum raw StatsBomb shot.statsbomb_xg *90 / minutes |
| pressures_p90 | PRESSURE events *90 / minutes, not successful pressures |
| recoveries_p90 | RECOVERY events *90 / minutes, not success rate |
| tackles_p90 | Duel subtype Tackle events *90 / minutes |
| interceptions_p90 | INTERCEPTION events *90 / minutes |

Implementation details that an acquisition must preserve:

- The touch proxy includes PASS, CARRY, SHOT, DRIBBLE and completed RECEIPT events. It counts event records, not distinct physical touches or time on the pitch. Multiple records can describe one possession chain.
- Coordinates are normalized to 0–100, attacking left-to-right, with y=0 on the attacker's left. Forward means end_x > start_x; progressive uses delta-x >= 10 with numerical tolerance. Incomplete passes may be forward but do not count as progressive/entries.
- The implemented proportional penalty box is x>=85 and 22.5<=y<=77.5. A physical pitch rectangle should not be substituted merely because it is also called a penalty area.
- Per-90 denominators use known appearance minutes, including the existing stoppage-time method. Missing endpoints invalidate the affected M2 rates; unknown minutes and absent measurements remain NULL.
- M2 eligibility requires at least 30 match minutes, at least 450 known season minutes, observed player events and finite values for all 15 inputs. A future pilot's sample targets do not change this existing contract.
- The 15 inputs do not include reception count or nearest-defender distance. Wirtz code computes separate reception summaries but leaves advanced nearest-defender output unimplemented. Tracking-time occupation is a new estimand, not an EXACT version of `halfspace_share`.

This extraction supersedes any loose paraphrase for Step 2 decisions without changing Step 1 files.

## Route A — public source candidates

Statuses apply to the inspected release, not every commercial product under the same name. A source is usable for this study only when both target matches and the required reuse rights are verified.

| Candidate and official evidence | Coverage / season / teams | Coordinates, identities, lineups, minutes, events | License/access and download | Real-Alonso usable? | Chelsea-Alonso usable? | Confidence |
|---|---|---|---|---|---|---|
| StatsBomb Open Data: [current catalog](https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json), [README](https://github.com/hudl/open-data/blob/master/README.md) | Leverkusen 2023/24 already local. Inspected catalog's La Liga ends at 2020/21; Premier League entries are 2015/16 and 2003/04. No target-period men's club competition found in the full catalog. | YES event types/times, player/team IDs and coordinates; lineups and endpoint fields in source format. Minutes are derived with existing method. Tracking is event-triggered 360 for selected games, not continuous tracking. | Public JSON research release with attribution conditions. Target download: NO entry verified. | NO in inspected catalog | NO in inspected catalog | HIGH for this snapshot |
| Wyscout/Pappalardo: [paper](https://doi.org/10.1038/s41597-019-0247-7), [events](https://figshare.com/articles/dataset/Events/7770599), [matches](https://figshare.com/articles/dataset/Matches/7770422/1) | Five domestic leagues 2017/18 plus Euro 2016 and World Cup 2018. Spanish/English club scope predates the target coach periods. | Event seconds, IDs and normalized start/end coordinates documented. Lineups/substitutions supplied; minutes can be derived with an explicit method. Carry/pressure taxonomy is not automatically StatsBomb-equivalent. | CC BY 4.0; public archive downloads. | NO | NO | HIGH |
| SkillCorner Open Data: [repository](https://github.com/SkillCorner/opendata), [match catalog](https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches.json) | A-League 2024/25; no target clubs. Catalog count differs from README; details below. | Player/team/lineup/minutes metadata and tracking available; dynamic events are not a complete StatsBomb-compatible event feed. | Open repository/MIT and attribution; footage rights not supplied. | NO | NO | HIGH for excluded scope |
| Metrica: [official samples](https://github.com/metrica-sports/sample-data) | Three historical sample games; named teams/competitions not established for study matching. | Synchronized events/tracking; anonymized identity. Full target-match minutes and named rosters UNKNOWN. | Public sample download; explicit experimentation scope; broader reuse UNKNOWN. Unusable for broader reuse unless clarified. | NO; no verified target match | NO; no verified target match | HIGH for rejection; real identities UNKNOWN |
| SoccerNet original action-spotting release: [original paper](https://arxiv.org/abs/1804.04527), [data page](https://www.soccer-net.org/data) | Original 500-match corpus covers 2014–2017. GSR is a separate release audited below. | Sparse action labels are not full pass/carry/player/endpoint data. No required target-period event feed verified. | Research-video access conditions/NDA; public labels do not grant unrestricted footage reuse. | NO for inspected original release | NO for inspected original release | HIGH |

Unverified third-party mirrors, unofficial score-site extraction and undocumented private endpoints are not eligible acquisition routes. No candidate was promoted to usable on the basis of a team name or a download button alone. All inspected source URLs are recorded above; no match/event/tracking dataset was constructed.

## Commercial/research access: concrete next request

[Hudl's product page](https://www.hudl.com/products/statsbomb) documents raw event delivery/API and a sales contact route. Its [FAQ](https://www.hudl.com/products/statsbomb/faq) distinguishes event data, event-linked visible-player 360 and broadcast tracking. [Opta's official product page](https://www.statsperform.com/products/opta-data/) and [licensing contact guidance](https://optaplayerstats.statsperform.com/en_GB/about) establish a legitimate alternative enquiry route. None establishes a current research entitlement or an exact inventory of the desired matches.

Prepare the following request for the user's review; **nothing has been sent**:

> Research scope: observed No.10-like player-match behaviour under Alonso across Bayer Leverkusen, Real Madrid and Chelsea. Please confirm exact completed match IDs/dates/competitions within the documented coach periods, including Real Madrid 2025-06-01 to 2026-01-12 and Chelsea from its verified July 2026 start through the agreed cutoff. Supply field/version documentation and permission for a small raw example. Required fields: player/team IDs and roster mapping, starting lineups/substitutions and reliable minutes, period/timestamp/event type/outcome, event locations, pass/carry endpoints, shot-assist qualifiers and xG model version, defensive event definitions. Please confirm research computation, local retention, derived feature publication, reproducibility by other authorized researchers, attribution and redistribution limits. Quote access conditions and costs; a research discount/grant is not assumed. State whether matched control periods are available. Quote synchronized video/tracking rights separately if offered.

Acceptance gate, before dataset work: written permission; exact eligible match manifest; required fields inspected in a permitted sample; coordinate conventions; missing-data and minutes rules; xG/taxonomy version equivalence; control-data route; immutable release/checksum references. If any feature is only APPROXIMATE, it stays in sensitivity analyses and does not enter the EXACT core. If there is no common exact core, return to the feasibility gate while retaining all three clubs.

## Development datasets: purpose and verified limitations

`tracking_dataset_audit.csv` contains the requested field-by-field audit and URLs. They are development resources; no verified Real/Chelsea Alonso observations are contributed.

**SoccerNet.** The GSR task supplies annotated pitch positions, track/role/team/jersey attributes and calibration support. Its benchmark is GS-HOTA. Proposed evaluation is legal clip → our predicted coordinates → held-out annotation comparison, including metre error and track association; full GS-HOTA is reported only with its required attributes. A clip-only MVP without jersey prediction cannot claim equivalent benchmark performance. [GSR documentation](https://github.com/SoccerNet/sn-gamestate); [submission representation](https://github.com/SoccerNet/sn-gamestate/blob/main/ChallengeRules.md).

The paper's annotation example uses 25 fps and 750 frames for 30 seconds. Ground positions depend on a foot/ground-plane construction and have annotation uncertainty; GSR v1 excludes ball reconstruction. [Primary paper](https://arxiv.org/html/2404.11335v1). The official FAQ limits the dataset to research and the Data page requires video NDA access. Code/dataset-card licenses must not be interpreted as clearing broadcast rights. Project access is not yet established. [FAQ](https://www.soccer-net.org/faq); [access](https://www.soccer-net.org/data).

**SkillCorner.** Use the audit's detected/extrapolated distinction in every feature. Do not treat these provider estimates as independent truth for evaluating a model using the same source footage. The current catalog has **20 entries**, while the README advertises **10 matches**. An entry is not proof of a complete released tracking file. Complete usable tracking count remains UNKNOWN. Official catalog IDs: 2017461, 2016236, 2015213, 2013725, 2011166, 2010085, 2007721, 2007448, 2006363, 2006229, 1996435, 1996436, 1986691, 1959846, 1953632, 1927964, 1925299, 1899585, 1886347, 1874553. [Catalog](https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches.json).

**Metrica.** Useful for event/frame joining and normalization within the stated sample-use permission. No independent video calibration benchmark or named Alonso match is established. Treat unverified broader redistribution rights as a blocker for that use. [Sample terms and format](https://github.com/metrica-sports/sample-data); [Game 3 metadata](https://raw.githubusercontent.com/metrica-sports/sample-data/master/data/Sample_Game_3/Sample_Game_3_metadata.xml).

## Broadcast route: feasible reduced MVP and limits

Proposed chain: rights-cleared clip → player detection → short-sequence tracking → team classification → camera calibration/homography → pitch coordinates → optional verified identity → explicitly supported No.10 features.

The reduced first MVP needs **one 20–30 second main-camera clip**, detected players only, a target track and nearby players, manual team labels if necessary, and manual removal of cuts/replays. Player names, ball reconstruction, automated possession labels, jersey OCR and full 22-player reconstruction are not needed for this technical step. When applied later to a named No.10, manual roster identity confirmation becomes mandatory.

A complete 22-player solution is **not required** to evaluate observed target locations and distances to visible neighbours. However:

- Nearest *visible* defender distance can exceed the true nearest distance when an unseen opponent is closer.
- Density of visible opponents is only a lower bound if the local area is partly off-screen.
- Distance to a specific striker/pivot requires both identities and both positions; do not infer their roles from formation labels alone.
- Visible-player width/depth is not full-team width/depth. Withhold whole-team shape unless the relevant entire team is observed.
- Missing off-camera positions cannot be recovered as measurements by smoothing or extrapolation.

| Family | Realistically obtainable from a short video? | Restriction |
|---|---|---|
| Time-weighted observed player position / half-space occupation | PARTIAL | Calibrated, visible frames only; state time denominator; different from M2 event-weighted features |
| Local distance / density | PARTIAL | Need relevant visible region and reviewed team labels; distinguish visible-only proxies |
| Striker/pivot distance | PARTIAL | Requires verified identity/context and co-visibility |
| Whole-team width/depth | PARTIAL | Only complete required team support; no whole-team claim from cropped broadcast |
| Passes/carries/shots/progressive actions | PARTIAL with separate reviewed event annotation | Continuous tracks alone do not identify ball actions or action endpoints |
| Shot assists | UNKNOWN until shot-chain annotation and definition are validated | Cannot copy provider flags from tracking |
| StatsBomb xG / defensive event taxonomy | NO exact recovery from video-only tracking | A new model or different labels would change the measurement contract |

The risk register distinguishes MUST SOLVE, CAN DEFER and NOT REQUIRED. Managing off-camera missingness is mandatory even though reconstructing all missing players is not.

## Paired Leverkusen validation — design only

**Legal matched-video route: UNKNOWN.** Bayer's official 2023/24 competition page lists match highlights, including the final Augsburg league match, but the inspected page does not confirm download, computational reuse or derived-data rights. Highlights also select attacking outcomes. They are not a legal/research-complete validation sample. [Official listing](https://www.bayer04.de/en-us/competition/202324-season/bundesliga). Obtain explicit rights to a matched, representative subset before processing; no video downloaded.

Conditional validation design:

1. Choose at least three legally usable 2023/24 Leverkusen league matches with different camera views/opponents and verified identity/clock alignment. Reserve one match for validation after all transformations and quality thresholds are fixed.
2. Select at least 50 matched eligible touch-proxy events per match across periods and phases, where available. If fewer exist, disclose the count and keep conclusions at pilot level.
3. At the **same event timestamps and same player**, compare ground-plane video positions to event origins after explicit orientation and coordinate conversion. An event ball/action location and estimated foot position are only compatible proxies, not identical physical truth.
4. Aggregate `avg_touch_x/y` and event-weighted `halfspace_share` using exactly the same matched event support. Also compare the visible-event subset with all source events to expose selection bias. Do not compare every video frame with an event-weighted M2 average.
5. Report coordinate MAE, Euclidean position error where metre conversion is justified, signed bias, Pearson correlation and Spearman rank correlation. At player-match level report MAE/bias/rank correlation for aggregates; undefined correlations from too few/constant observations are UNKNOWN.
6. Cluster uncertainty summaries by match; never treat thousands of correlated video frames as independent matches. Stratify error by camera region, occlusion, identity confidence and field visibility. Inspect disagreement plots. High correlation alone does not establish agreement.
7. Time-weighted positioning has no continuous StatsBomb ground truth. Event-linked 360 can support same-time visible-context checks only after existing UUID linkage and identity limitations are respected. It cannot validate unobserved trajectories or full-match off-ball occupation.

Proposed engineering gates, not observed results or statistical power: median held-out position error <=2 m and 90th percentile <=5 m where a valid metre reference exists; event-normalized axis bias <=2 pitch units; aggregate half-space difference <=0.05 on matched support. Record errors even when gates fail. The tolerances are provisional and must be justified against the eventual minimum football effect of interest; passing them does not relabel an APPROXIMATE feature EXACT.

## Compare the two video designs

| Design | Pros | Measurement bias / validity | Feasibility / workload |
|---|---|---|---|
| DESIGN 1: HYBRID; Leverkusen events, Real/Chelsea video | Reuses baseline; less Leverkusen footage work | HIGH bias risk: source method is confounded with club; time/event sampling differs; paired validation cannot fix a different estimand | Current feasibility UNKNOWN; engineering HIGH; rights needed for external clubs and Leverkusen validation |
| DESIGN 2: COMMON VIDEO; all three clubs processed identically | Shared sampling/annotation/visibility rules; StatsBomb remains Leverkusen reference | Lower method asymmetry in principle, but camera/league/phase selection still confounds results; tracking still does not provide events | Current feasibility UNKNOWN; engineering HIGH and more manual coverage than HYBRID; footage rights for all clubs |
| Recommended OTHER: common event provider with verified definitions | Closest to existing behavioural contract; reproducible field-level matching | Still audit schema/xG version drift, minutes and collection conventions; no causal conclusion | Access/price UNKNOWN; engineering MEDIUM conditional on permission |

If a video-only branch is approved later, COMMON VIDEO is methodologically preferable to unvalidated HYBRID for newly defined spatial measures. That is not the selected primary route today and would require a new compatibility review. RAW → standardized features → PCA → similarity → neural last remains the later analysis order; nothing is fitted here.

## Practical sample gates, not statistical power

These are proposed planning thresholds, not claims that such matches or No.10 candidates are available. All three clubs must satisfy their own gate; none may be dropped. Count independent matches and named player-match observations separately.

| Quantity per club | PILOT SAMPLE | FINAL PRELIMINARY STUDY SAMPLE |
|---|---|---|
| Verified eligible matches | 2 | At least 10 against at least 5 opponents |
| Documented No.10-role minutes | At least 120 summed candidate minutes | At least 600 summed candidate minutes |
| Distinct eligible player-match observations | At least 2, each with >=30 role minutes | At least 10, each with >=30 role minutes |
| Candidate diversity | One verified candidate can test mechanics | Aim for >=2 players with >=3 matches each; if unavailable, explicitly limit player-vs-role inference |
| Accepted visible possession/phase units for video branch | >=20 per club, >=8 in each match | >=150 per club, >=10 in each match |
| Target-visible duration within a retained phase | >=80% | >=90% |
| Accepted phase coverage of eligible team possessions during target role minutes | >=30% per match | >=60% per match |
| Team/identity/clock checks | All retained units manually reviewed | All ambiguous units reviewed; pre-registered QC sample plus all failures |
| Event-source coverage in recommended route | Complete agreed event/lineup record for pilot matches; missingness disclosed | Complete agreed record for every included match; each EXACT feature's required fields verified |

Coverage is a measured fraction, not a confidence score. Its denominator must come from a full licensed event/video log: eligible possessions while the candidate is on-field in the documented role. If the denominator cannot be measured, coverage is UNKNOWN and the gate cannot pass. Also report actual accepted visible seconds / all eligible in-possession seconds, to detect many short selected phases. Never convert selected-phase counts to whole-match per-90 rates.

The final preliminary sample is still small. **One or two matches do not represent a coach's full system.** Include home/away and multiple score/formation contexts where actually available; report missing strata rather than inventing balance. Apply the same sampling rules to Control A (same club pre/post period) or, if infeasible, Control B (matched league/season AMs). Ask suppliers for control coverage in the same request. No powered or causal claim is justified by these targets.

## Internal schema and source coexistence

`proposed_tracking_schema.csv` describes tracking and optional event records. YES in its required column means the field must be present; nullable types explicitly allow unknowns. Both record types retain coordinate/identity confidence, calibration error, visibility fraction and source method. Quality categories are LOW/MEDIUM/HIGH/UNKNOWN with auditable rules, not invented numeric ratings.

A track ID is clip/segment-scoped and distinct from a real player ID. Preserve period, source frame/timebase and clip offset; clock alignment may remain unknown. Native coordinate units and physical dimensions must be retained. Metres, normalized coordinates and attacking direction are converted only with explicit metadata. Confidence from different providers is not assumed calibrated or comparable.

StatsBomb events use event records; 360 rows, if used later, are event-linked snapshots with frame/track IDs null where absent. SkillCorner-like records preserve detected/extrapolated status. SoccerNet annotations and future predictions have distinct source_method values. Null calibration error for provider events means unreported/not applicable, not perfect accuracy. Schemas coexist without pooling unequal measurements.

## Conditional clip specification; not selected or built

If the user later selects C after rights review: one legal short clip in, schema-conforming timestamp/track_id/team/x/y/confidence rows and a reviewed overlay out. Anonymous player IDs are allowed, team labels may be clip-scoped, and unknown match-clock alignment is stored explicitly alongside clip time.

Success requires detected visible players; at least one target track maintained for a continuous 10-second segment with every switch/gap logged; reviewed separable team labels; a nondegenerate transform supported by distributed pitch landmarks and held-out error; an overlay reviewed at the beginning/middle/end and during camera motion; and valid saved records preserving missingness/uncertainty. Plausible appearance alone is insufficient; evaluate against SoccerNet labels when access permits. Names, ball and events remain outside this first technical MVP.

## Verification and stopping point

Existing unchanged suite: `.venv/bin/python -m pytest -q` → **83 passed, 20 subtests passed, 0 failed**. No new tests or production code added. Repository safety is checked against hashes captured before Step 2 writes, including all Step 1 files and protected data/models/outputs/UI.

Only the six requested Step 2 deliverables are added. No supplier contact, contract acceptance, dataset construction, full tracking download, video acquisition, PCA, training or UI work was performed. Next action is a reviewed access request and match/rights/schema confirmation, not automatic implementation.
