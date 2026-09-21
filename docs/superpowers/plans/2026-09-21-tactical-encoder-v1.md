# Tactical Encoder v1 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. Track steps here.

**Goal:** Complete the user's Milestone 3 and stop.
**Architecture:** Reuse M2 raw feature artifact and constants. Separate data contract,
model/training, evaluation, interpretation, inference, plots/report and entry point.
**Tech Stack:** Existing NumPy, sklearn, PyArrow, matplotlib; CPU torch only added runtime.
**Spec:** docs/superpowers/specs/2026-09-21-tactical-encoder-v1.md

## Global constraints
- 376 rows / 34 matches / 18 players / 15 features; no ingestion or M2 changes.
- Train-only scaler/PCA; validation-only checkpoint selection; 10 fixed seeds.
- Seven figures visually inspected; two full runs; full pytest at end.
- User requests no questions and authorizes execution of the supplied detailed spec.

## Review focus
- Self-neighbours and singleton players must not bias evaluation.
- Shape, duplicate-column and nonnumeric schema errors must be explicit.
- Wirtz rows must be removed before prototype eligibility is recomputed.
- Test features cannot influence scaler, training or checkpoint selection.
- Verdict uses paired improvements and joint wins, never pooled embeddings.

## Task 1: Core data/model/evaluation contract
Files: tests/test_tactical_encoder.py; src/models/tactical_encoder.py;
src/models/encoder_evaluation.py.
- [x] Write failing tests: canonical ordering and metadata exclusion, disjoint match
  groups, train-only scale, real-row 4-D encoding and weight reload, neighbour and
  cohesion definitions and joint-win verdict.
- [x] Run `.venv/bin/python -m pytest tests/test_tactical_encoder.py -q`; expect missing module failures.
- [x] Implement load_m2(), feature_matrix(), split_matches(), prepare_split(),
  TacticalAutoencoder, train_autoencoder(), evaluate_run(), summarize_runs().
- [x] Run same tests; expect pass.

## Task 2: Inference and descriptive outputs
Files: src/models/inference.py; src/models/encoder_interpretation.py;
tests/test_tactical_inference.py.
- [x] Write failing tests for inference schema, feature ordering, range flags,
  saved reload, prototype thresholds and Wirtz exclusion.
- [x] Implement artifact serialization and inference using persisted feature order,
  train centre/ranges and eligible prototype data; compare_to_role_prototypes().
- [x] Implement season/prototype/Wirtz and autograd interpretation summaries.
- [x] Run both new test files; expect pass.

## Task 3: End-to-end outputs and evaluation
Files: src/models/train_tactical_encoder.py; src/analysis/tactical_encoder_plots.py;
src/analysis/tactical_encoder_report.py; requirements.txt; README.md.
- [x] Pin installed CPU torch, document pytest as environment test tool only.
- [x] Implement one command to run seeds 42..51 and save requested artifacts and metrics.
- [x] Generate report tables from saved metrics.json and seven PNG figures.
- [x] Execute full command, inspect metrics, add only supported narrative logic.
- [x] Execute command again; confirm seed-42 MSE difference <=1e-5.
- [x] Open all seven final figures, run final full pytest, independent review.
- [x] Record verification evidence and give requested final format; stop.

## Execution ledger
Preflight: M2 files and metadata inspected. Exact data assertions pass. Existing
pytest: 61 passed, 20 subtests passed. Torch initially absent; CPU build requested.
Ruling: pytest installed as requested test runner, not a project runtime dependency.
Ruling: work in user-specified directory; git executable unavailable and no local
.git checkout metadata. Record unavailable git commit instead of creating a repo.
Ruling: user's complete specification/no-questions instruction supersedes skill
approval handoffs. Execute inline, with a final independent review as prescribed.

Final verification: 79 passed, 20 subtests passed in 8.96s.
Two full fixed pipelines completed; seed-42 MSE delta=0.0.
All seven figure bytes visually checked; pale legend text corrected and revised figures re-opened.
Independent review: Arrow Table columns are arrays, not names. Reproduced failure, corrected name selection, regression test passed.
Review test gaps addressed: nonidentical nearest-neighbour sets and separate versus joint wins.
Reviewer deferred actual two-run/figure/full-suite verification to primary agent; all completed above.
No Critical or Important issue remains. M2 files retain their original manifest hashes.
