# Alonso Tactical Role Encoder v1

The user's Milestone 3 specification is the binding design. Build a CPU-only baseline
15→12→8→4→8→12→15 GELU autoencoder from M2's 376 eligible rows, 34 matches,
18 players and ordered 15 raw tactical features. Identity and context never enter
training. No ingestion, new tactical features, downstream teams or application UI.

Split sorted match IDs by seeded permutation: 24 train, 5 validation, 5 test. Fit
StandardScaler and sklearn PCA(4, full SVD) on training rows only. Adam 1e-3,
weight decay 1e-5, batch 32, max 500 epochs, patience 40, validation selection,
restore best checkpoint. Linear bottleneck and output; GELU on hidden layers.
Run split/model seeds 42 through 51, save seed 42, no tuning after test inspection.

Evaluate overall/per-feature reconstruction, top-5 Euclidean neighbour overlap,
same-player/different-player distance ratio among players with at least two test
rows, and dimension variance. Collapse threshold: variance <=1e-6 (absolute).
Mean reference is the training mean. Report sample std across runs. Clearly better
requires >=8 joint reconstruction/overlap wins AND mean paired improvement greater
than sample std of paired improvements for EACH metric. Otherwise use the exact
required comparable-or-worse statement; no superiority claims from cohesion.

Season centroids, prototype centroids and variances are unweighted across eligible
matches (population std/variance). Position groups use nominal_position, complete
in M2. Require 20 rows and two players after any Wirtz exclusion. Prototype and
season summaries use all rows descriptively; never feed them back into evaluation.
Train rows fit weights, validation rows select checkpoint; both are in-sample for
model development. Held-out tests are used only after best checkpoint selection.

Inference accepts mappings, lists of mappings, Arrow tables and dataframe-like
objects via to_dict(orient='records'), without adding pandas. Reorder by saved
feature_order.json, reject missing/non-numeric/non-finite features, warn and ignore
extra columns. Return 4-D embedding, availability, train-range flags and centred
cosine/Euclidean prototype comparisons. State dicts loaded with weights_only=True.

Save all requested artifacts, per-run metrics and loss histories, seed-42 embeddings,
prototype and Wirtz summaries, seven inspected PNGs, and a report rendered from
saved metrics.json. Report generation initially contains factual tables and fixed
methodology; supported narrative observations are added after inspecting outputs.
