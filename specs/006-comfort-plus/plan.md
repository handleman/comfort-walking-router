# 006 Comfort-Plus — Plan

## Approach
Scorer slice: extend the 001 scorer with two equal-weight toggle factors sourced from the existing Overpass corridor data, additive contract, explanation honesty on tag gaps. Reference spec AC-1..AC-5.

## Steps
1. Tag mapping: `lit` + road-class → factor inputs in the corridor lookup (fixtures for lit/unlit, road classes) (AC-1, AC-2, AC-3).
2. Scorer: `prefer_lit` + `avoid_traffic` toggles, equal weights; explanation lists active factors + data-gap notes (AC-2, AC-4).
3. Additive contract fields + UI toggles (AC-1, per ADR-005).
4. Regression: full 001 suite green + scorer matrix + gates (AC-4, AC-5).

## Risks / Open Questions
- OSM `lit` coverage is patchy — honest-gap explanation is the mitigation, not interpolation.
- Depends on 001 (scorer, contract); independent of 004/005/007/008.
