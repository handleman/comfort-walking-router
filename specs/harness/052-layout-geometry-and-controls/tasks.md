# 052 Layout Geometry & Control Presence — Tasks

Each task maps to one acceptance criterion.

- [ ] T1 (AC-6): `specs/product/040-google-maps-layout/layout.toml` — regions (top_card, map, sidebar, drawer), controls (origin/dest inputs, start_walk, comfort_legend, handles), per-viewport `visible_regions`/`hidden_regions`.
- [ ] T2 (AC-6): `swarm/acceptance.py` — `LayoutContract` parser for `layout.toml` (regions/controls/expect); a Figma-shaped fixture (layer names → `data-testid` selectors) parses identically.
- [ ] T3 (AC-1): `frontend/scripts/acceptance.mjs` — collect `layout_facts` per viewport (`getBoundingClientRect` + visibility for every region/control).
- [ ] T4 (AC-1): check kinds `present` + `unique` (exists, visible, non-zero rect, unique where flagged) with explicit tolerances.
- [ ] T5 (AC-2): check kind `in_region` (control rect contained in its region rect ± `tolerance_px`).
- [ ] T6 (AC-3): check kinds `region_visible`, `region_hidden`, `region_order`, `no_overlap`, `no_overflow`.
- [ ] T7 (AC-5): geometry failures flow through `queue_fix_tasks` (043) as `T<n>` tasks naming the control/region + assertion.
- [ ] T8 (AC-4): test that the checks read only `layout_facts` (no screenshot, no vision, no network beyond fixtures).
- [ ] T9 (AC-7): `swarm/tests/test_acceptance.py` — pass + fail per kind, the Figma-shaped fixture, and a queued-fix assertion.
- [ ] T10 (AC-7): `make test`, `make e2e`, `make swarm-test`, `ruff check .`, `mypy app tests` green.
