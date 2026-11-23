# 052 Layout Geometry & Control Presence — Tasks

Each task maps to one acceptance criterion.

- [ ] T1 (AC-5): `specs/product/040-google-maps-layout/layout.toml` — regions (top-card, map, sidebar, drawer), controls (origin-input, dest-input, start-walk, comfort-legend, handles) with candidate regions, per-viewport `visible_regions`/`hidden_regions`, `[tolerance]`.
- [ ] T2 (AC-5): `swarm/acceptance.py` — parse `layout.toml` into a `LayoutContract`; a Figma-shaped fixture (layer names → `data-testid`) parses identically.
- [ ] T3 (AC-1): `specs/product/040-google-maps-layout/tasks.md` **T22** (product task, swarm implements) — add kebab-case `data-testid` to the Svelte controls/regions.
- [ ] T4 (AC-1): `frontend/scripts/acceptance.mjs` — for the two states (no-route, route-planned) and two viewports, emit `layout_facts` (rects, visibility, peer map).
- [ ] T5 (AC-1): kinds `present` + `unique` (visible = rendered, non-zero, in scroll flow).
- [ ] T6 (AC-2): kind `in_region` against the control's candidate regions (± `tolerance.px`).
- [ ] T7 (AC-3): kinds `region_visible`, `region_hidden`, `region_order`, `no_overlap` (peers only), `no_overflow`.
- [ ] T8 (AC-4): a geometry failure is an AC FAIL → `queue_fix_tasks` names control/region + assertion.
- [ ] T9 (AC-4): test that checks read only `layout_facts` (no screenshot/vision/extra network).
- [ ] T10 (AC-6): `swarm/tests/test_acceptance.py` — pass + fail per kind, the Figma-shaped fixture, a queued-fix assertion; then `make test`, `make e2e`, `make swarm-test`, ruff, mypy green.
