# 006 Comfort-Plus — Spec

## What / Why
Deepen comfort scoring with two toggleable factors — street lighting and low-traffic preference — from OSM tags, keeping the toggles-only UX (equal weights). v1 "quiet" becomes explicit traffic avoidance.

## Scope
- In scope:
  - `prefer_lit`: favor ways tagged `lit=yes`; where lighting data is absent, say so in the explanation instead of guessing.
  - `avoid_traffic`: down-weight high-class roads (primary/secondary/trunk) and up-weight footpaths/residential; builds on v1 quiet.
  - Toggles in UI (on/off, equal weight with shade/sun/quiet); additive contract fields per ADR-005; explanation lists every active factor.
  - OSM tag lookup folded into the existing Overpass corridor query (no new provider).
- Non-goals:
  - No surface/step-free factors (deferred; needs better OSM coverage analysis).
  - No ranked weights or per-factor sliders (toggles only by design).
  - No live traffic data (OSM road-class heuristic only).

## Acceptance Criteria
- [ ] AC-1: Each toggle on/off flips scoring on a fixture pair (lit vs unlit; busy vs quiet) deterministically.
- [ ] AC-2: `prefer_lit` routes via lit ways where tagged; explanation notes honest gaps (`lighting data unavailable here`).
- [ ] AC-3: `avoid_traffic` avoids high-class roads for a quieter alternative at modest detour cost.
- [ ] AC-4: No MVP regression — 001 suite (shade/sun/quiet, cache, contract) green unchanged.
- [ ] AC-5: `pytest` + `ruff check .` + `mypy .` + `npm run check` clean; scorer matrix unit-tested.
