# 052 Layout Geometry & Control Presence — Plan

References `specs/harness/052-layout-geometry-and-controls/spec.md` AC-1–AC-7.

## Approach

DOM-only, deterministic, source-agnostic. Build one geometry fact snapshot per
viewport, assert against a declarative IR, and let 043's existing failure path
turn a breach into a fix task. The Figma path is a seam, not code, in this pass.

## Steps

1. **IR + parser (AC-6).** Add `layout.toml` (regions, controls, per-viewport
   expectations) and a parser in `swarm/acceptance.py` producing a plain dict
   (`LayoutContract`). A fixture with Figma-shaped layer names (→ selectors via
   `data-testid`) proves the parser is source-agnostic.
2. **Fact collector (AC-1..AC-3).** Extend `acceptance.mjs`: for every region and
   control, capture `getBoundingClientRect()` + visibility (`offsetParent`,
   `getComputedStyle`), and emit `layout_facts` per viewport alongside the
   existing `views`.
3. **Check kinds (AC-1..AC-3).** Add `present`, `unique`, `in_region`,
   `region_visible`, `region_hidden`, `region_order`, `no_overlap`, `no_overflow`
   to `CHECK_KINDS` + the runner, with explicit tolerances
   (`tolerance_px`, `overlap_max_px`).
4. **Wire failures (AC-5).** A geometry failure is a `Check` result, so
   `queue_fix_tasks` (043) appends the `T<n>` fix task naming the control/region
   and the assertion — no new path.
5. **Determinism (AC-4).** Assert the checks read only `layout_facts` (no
   screenshots, no vision); the runner already blocks network except fixtures.
6. **Tests (AC-6, AC-7).** `swarm/tests/test_acceptance.py`: one test per kind
   (pass + fail), one for tolerance, one for the Figma-shaped fixture, one that a
   failure queues a task.
7. **Verify (AC-7).** `make test`, `make e2e`, `make swarm-test`, ruff, mypy.

## Risks

| Risk | Mitigation |
| --- | --- |
| Geometry tolerance too tight (1px borders/scrollbars) | explicit `tolerance_px`, tested at the boundary |
| Multiple "controls" regions (sidebar on desktop, drawer on mobile) | `region` may name a set; `visible_regions` picks the active one per viewport |
| Leaflet async tiles shift the map rect | compare regions relative to the layout, mask/margin the tile pane, assert the container not the tiles |
| Figma layer names drift | selectors resolved from stable `data-testid`; the mapping table is the contract |
| Duplicating the existing global facts | extend, do not re-implement `zeroSize`/`overflow`; geometry reuses them |

## Rollback

The IR + checks are additive; removing `layout.toml` and the new kinds restores
today's advisory-only behaviour.
