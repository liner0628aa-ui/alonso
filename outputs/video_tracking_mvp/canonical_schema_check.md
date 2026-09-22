# Canonical schema check

Spatial Engine integration: NOT RUN

Authority: src.spatial.coordinates.canonical_table, unchanged.
Shared stadium-frame x_m/y_m on the 105x68 reference pitch; never clipped.
Anonymous player_id=NULL; segment-scoped track_id; directions supplied per team.
coordinate_confidence=NULL and identity_confidence=NULL; no invented probabilities.
Unknown team blocks canonical export. Untracked and explicitly excluded people stay in source/QC.
Frame times use configured period clock plus validated constant-rate frame offsets.
Zero-detection frames are retained in frame_ledger.json; no fabricated coordinates.

Synthetic prescribed-box adapter -> existing Spatial Engine: PASS. See synthetic_validation in quality_summary.json. Real video: NOT RUN.
