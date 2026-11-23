# 052 Layout Geometry & Control Presence — Tasks

Each task maps to one acceptance criterion.

- [ ] T1 (AC-5): `specs/product/040-google-maps-layout/layout.toml` — **blocked on T22** (the `data-testid`s must exist first; authoring it early would fail every run).
- [x] T2 (AC-5): `swarm/layout.py` — `load_layout()` parses regions/controls/expect/tolerance; a Figma-shaped fixture test proves the IR is source-agnostic.
- [x] T3 (AC-1): `specs/product/040-google-maps-layout/tasks.md` **T22** (product task, swarm implements) — add kebab-case `data-testid` to the Svelte controls/regions.
- [~] T4 (AC-1): `frontend/scripts/acceptance.mjs` — emits `layout` facts (`regions`, `controls`, `overlaps`, `overflow`) per viewport; the no-route state is wired, the route-planned state is not yet.
- [x] T5 (AC-1): kinds `present` + `unique` (visible = rendered, non-zero, in scroll flow).
- [x] T6 (AC-2): kind `in_region` against the control's candidate regions (± `tolerance.px`).
- [x] T7 (AC-3): kinds `region_visible`, `region_hidden`, `region_order` (`above`), `no_overlap` (peers only, computed in the `.mjs` by ancestry), `no_overflow`.
- [x] T8 (AC-4): `SpecReport.layout_failures` gates the verdict and flows into `queue_fix_tasks` with the control/region's `ac`.
- [x] T9 (AC-4): the evaluator is pure (facts in, issues out); tests cover pass + fail per kind with no browser.
- [~] T10 (AC-6): `pytest swarm/tests/` (790), `ruff` clean. Real acceptance run pending T1/T22.
