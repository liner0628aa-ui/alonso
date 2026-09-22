CAN START CROSS-CLUB ANALYSIS NOW: PARTIAL
Exact common features: 0 | Approximate: 0 | Unavailable/unknown: 15
Leverkusen usable players/matches: 18 eligible role-vector players / 34 matches (376 player-match vectors)
Real Madrid usable players/matches: 0 verified / 0 verified; actual availability UNKNOWN
Chelsea usable players/matches: 0 verified / 0 verified; actual availability UNKNOWN
Biggest data blocker: No free/legal, feature-compatible event/lineup/XY/minutes datasets for Real Madrid 2025/26 or Chelsea 2026/27 are verified in the repo or by an approved source.

## Decision Gate: C — current public data insufficient

The local Leverkusen source is usable and all 15 generic features are EXACT there. Real Madrid and Chelsea have no verified rows or approved, feature-compatible public source in this audit. Therefore the three-club EXACT-only intersection is empty. Gate A is not supported, and Gate B cannot be run because the reduced common feature set has zero verified features. Acquire or derive legal, schema-compatible external data first.

## Counts and interpretation

Across the 45 club-feature cells, compatibility is EXACT 15 (Leverkusen), APPROXIMATE 0, UNAVAILABLE 0, and UNKNOWN 30 (Real Madrid and Chelsea). Across all three clubs, the exact common-feature count is 0. No missing external feature is filled with zero.

## Operational scope

Wirtz and Hofmann are verified local candidates only. Bellingham, Güler and Palmer remain unverified candidates with no local Alonso-match sample. The No.10 rule must combine nominal position, measurable on-ball behaviour and match context; it cannot be reduced to an attacking-midfield label.

## Next evidence needed

1. Confirm a free/legal Real Madrid Alonso-period and Chelsea Alonso-period source for match events, lineups, coordinates, minutes and any 360/tracking fields.
2. Verify provider definitions against the 15 definitions in `feature_compatibility.csv`.
3. Re-run the compatibility audit and only then construct a cross-club dataset and controls.
