# 052 Layout Geometry & Control Presence — Plan

References `specs/harness/052-layout-geometry-and-controls/spec.md` AC-1–AC-6 and
the resolved decisions table (2026-11-23).

## Approach

DOM-only, deterministic, source-agnostic. One `layout_facts` snapshot per
(viewport × state), assert against `layout.toml`, and let 043's existing failure
path turn a breach into a fix task. The Figma path is a seam, not code, in this
pass.

## Steps

1. **Contract (AC-5).** Author `specs/product/040-google-maps-layout/layout.toml`
   (regions, controls with candidate regions, per-viewport expectations,
   tolerances) using `data-testid` selectors. Parser + a Figma-shaped fixture test
   in `swarm/acceptance.py`.
2. **`data-testid` attributes — a product task (AC-1).** Add `specs/product/040/
   tasks.md` **T22**: kebab-case `data-testid` on the controls/regions
   (`origin-input`, `dest-input`, `start-walk`, `comfort-legend`, `top-card`,
   `sidebar`, `drawer`, `map`, `sidebar-handle`, `drawer-handle`). The swarm
   implements it; the harness only consumes it.
3. **Fact collector (AC-1..AC-3).** Extend `acceptance.mjs`: for the two states,
   capture rects + visibility for every region/control and the peer map, emit
   `layout_facts`.
4. **Check kinds (AC-1..AC-3).** `present`, `unique`, `in_region`,
   `region_visible`, `region_hidden`, `region_order`, `no_overlap`,
   `no_overflow`, with the `[tolerance]` block.
5. **Gate + queue (AC-4).** A geometry failure is a `Check` result → FAIL verdict
   + `queue_fix_tasks` names the control/region + assertion.
6. **Determinism (AC-4).** Tests assert checks read only `layout_facts` (no
   screenshot, no vision, no network beyond fixtures).
7. **Verify (AC-6).** `make test`, `make e2e`, `make swarm-test`, ruff, mypy.

## Risks

| Risk | Mitigation |
| --- | --- |
| Tolerance too tight (borders/scrollbars) | explicit `[tolerance].px`, boundary-tested |
| Peer/ancestor overlap confusion | compute peers by DOM ancestry; ancestors excluded |
| Collapsed drawer controls look hidden | visibility = rendered + in scroll flow, not above-the-fold |
| Two states double the authoring | start with 040; expected-control list is short |
| Figma layer names drift | selectors are `data-testid`; the mapping key is stable |
| T22 is an app change | it goes through the queue (AGENTS.md), not a direct edit |

## Rollback

Remove `layout.toml` + the new kinds; the pass returns to advisory-only.
