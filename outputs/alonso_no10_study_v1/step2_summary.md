# Alonso No.10 Study v1 — Step 2 summary

Audit date: 2026-09-22. All linked sources accessed on this date.

**DECISION: B — obtain legitimate provider/research access before coding.**

Actual public Real Madrid-Alonso/Chelsea-Alonso event dataset found: **NO**.
Existing Leverkusen availability is unchanged; Step 1 Decision C remains supported.
Exact shared three-club feature count: **0 verified**.
All three clubs remain in the study.

## Recommended acquisition and design

Request Hudl StatsBomb raw events/lineups first, with exact match IDs, coach/date confirmation, player identity, minutes, endpoints, event qualifiers, schema/model versions and explicit research rights. Provider target-match coverage, price and permission remain **UNKNOWN**. The [official product/contact route](https://www.hudl.com/products/statsbomb) establishes a way to ask, not an entitlement. An alternative provider requires a common, explicitly verified feature definition set for all three clubs.

Design: **OTHER — common event provider and verified definitions**. HYBRID video/event measurement confounds source with club. COMMON VIDEO is the preferable conditional video design for a new spatial study but needs footage rights and validation; it is not selected today.

## New evidence, without changing Step 1

- Real Madrid: the [official termination](https://www.realmadrid.com/es-ES/noticias/club/comunicados/comunicado-oficial-xabi-alonso-12-01-2026) dated 2026-01-12 limits the actual Alonso period; the initial contract end in Step 1 is not proof of tenure through 2028.
- Chelsea: [official appointment](https://www.chelseafc.com/en/news/article/xabi-alonso-appointed-chelsea-manager) and [July/2026–27 start context](https://www.chelseafc.com/en/news/article/mcfarlane-reacts-to-really-exciting-xabi-alonso-appointment) are now verified. Actual study match counts and player availability remain UNKNOWN.
- SkillCorner: official [catalog](https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches.json) has 20 entries despite the README's 10-match description. Complete usable tracking count is UNKNOWN. No target clubs occur in that catalog.

## Development resources

- SoccerNet: coordinate/calibration/tracking error benchmark, subject to research/video access terms. No verified target Alonso match; partial anonymous MVP performance must not be presented as full GS-HOTA.
- SkillCorner: geometry and visibility-aware feature prototyping; distinguish predictions and extrapolations from reference ground truth.
- Metrica: synchronized event/tracking join and normalization experiments within explicit sample-use scope; broader reuse rights are UNKNOWN.

See tracking_dataset_audit.csv for official URLs, units, frame rates, identity limits, access conditions and unresolved fields.

## Video MVP and risks

No MVP built. Conditional future input: one rights-cleared 20–30 second main-camera clip. Output: timestamp, track_id, team, x/y, categorical confidence and uncertainty in proposed schema, with reviewed overlay. Stable anonymous tracks, separable teams, measured pitch calibration and saved schema are the initial success criteria.

Must solve: footage rights, moving camera calibration, cut/replay exclusion, short-track switches/occlusion, team labels, timebase, visibility/coverage and source-method bias. Manual identity confirmation is needed before named-player study use.

Can defer: automatic jersey/name recognition, cross-cut identity linking, ball and event reconstruction. Full 22-player off-screen tracking is not needed for a local spatial MVP; full-team or unseen-neighbour claims are withheld.

## Validation and sampling

Legal paired Leverkusen video processing route: **UNKNOWN**. Official highlight availability does not establish computational reuse rights or representative coverage. Conditional validation matches identical player/event times, compares coordinates and event-weighted spatial summaries using MAE, signed bias, Pearson and Spearman correlations, and separately measures visible-sample bias. Continuous frame-weighted positions cannot be validated as M2 touch-weighted means.

Proposed per-club pilot: 2 matches, >=120 documented No.10 minutes, >=2 player-match observations and >=20 visible phases. Final preliminary study: >=10 matches, >=600 minutes, >=10 observations and >=150 phases. Coverage gates and denominators are specified in the report. These are practical thresholds, not power calculations. One or two matches do not describe a coach's full system.

## Deliverables and checks

Created only:
- step2_data_acquisition_report.md
- data_acquisition_routes.csv
- tracking_dataset_audit.csv
- proposed_tracking_schema.csv
- video_pipeline_risk_register.csv
- step2_summary.md

Existing suite unchanged: **83 passed / 0 failed; 20 subtests passed**.
Existing files modified: **NONE** (checked against the pre-write content hashes).

NEXT MINIMUM ACTION: review the provider-access request in the report, then obtain an exact match inventory and explicit research-use permission. Do not start data construction until those gates and definition equivalence pass. No external enquiry has been sent.

STOP.
