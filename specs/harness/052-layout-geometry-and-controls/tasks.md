# 052 Layout Geometry & Control Presence — Tasks

Each task maps to one acceptance criterion.

- [x] T1 (AC-5): `specs/product/040-google-maps-layout/layout.toml` — regions (top-card, map, sidebar, drawer) + controls (origin/dest inputs, start-walk, comfort-legend) with candidate regions, `viewports` where the region is open by default, per-viewport visible/hidden, tolerance.
- [x] T2 (AC-5): `swarm/layout.py` — `load_layout()` parses the IR; a Figma-shaped fixture test proves it is source-agnostic.
- [x] T3 (AC-1): product **040 T22** — the swarm added the kebab-case `data-testid` attributes (`origin-input`/`dest-input` render as `data-testid={testId}` on the SearchInput root).
- [~] T4 (AC-1): `frontend/scripts/acceptance.mjs` emits `layout` facts; the **no-route state** is wired and verified. The route-planned state and the mobile-drawer-open state are pending.
- [x] T5 (AC-1): `present` + `unique` (visible = rendered, non-zero, display/visibility/opacity — **not** `offsetParent`, which is null for `position: fixed`).
- [x] T6 (AC-2): `in_region` against the control's candidate regions (± `tolerance.px`).
- [x] T7 (AC-3): `region_visible`, `region_hidden`, `region_order` (`above`, for tiled layouts), `no_overlap` (peers only), `no_overflow`.
- [x] T8 (AC-4): `SpecReport.layout_failures` gates the verdict and flows into `queue_fix_tasks` with the control/region's `ac`.
- [x] T9 (AC-4): the evaluator is pure; 11 tests cover pass + fail per kind and per-viewport control scoping, no browser.
- [x] T10 (AC-6): 793 swarm tests, ruff clean; **a real acceptance pass on 040 reports `layout_failures: NONE`** at desktop + mobile.
