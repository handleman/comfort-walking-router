# 052 Layout Geometry & Control Presence — Spec

Harness spec (control plane; the queue never runs it).

**Status:** designed + decisions resolved 2026-11-23; implementation pending.

## Problem

Layout verification today is **advisory and ad-hoc**:

- the acceptance pass (`frontend/scripts/acceptance.mjs`, 043) drives Playwright,
  but its per-AC probes are hand-written `exists / absent / count / min_count /
  text / value_set / route_request` checks in `acceptance.toml`, plus a few global
  facts (`zeroSize`, `overflow`, `duplicateButtons`, `tiles`, `leaflet`,
  `consoleErrors`);
- a vision model adds a second opinion, but it is non-deterministic and cannot
  gate a commit;
- there is **no geometry**: nothing asserts that a control sits in the region it
  belongs to, that regions tile the viewport, or that peer controls do not
  overlap;
- the expected-control list is scattered, so "the sidebar has the handles it
  should" is only checked where someone remembered a probe.

Consequence: a layout task (040 `T6`-class, "verify the layout") is a
*meta-verification* task the coder cannot satisfy by writing code — it parks as
`e2e_unclassified` because the required evidence is a recorded Playwright run the
coder never produced. Verification must be **harness-owned and deterministic**.

## Goal

Deterministic, screenshot-free verification of two things, per viewport, in the
two states that matter (initial no-route page, and after a route is planned):

1. **Control presence** — every control the layout promises exists, is visible,
   and is unique where flagged.
2. **Basic geometry** — each control sits inside its declared region; regions
   tile the viewport as declared (top card above map; sidebar on desktop, drawer
   on mobile, never both); peer controls do not overlap; no horizontal overflow.

The same checks are the pass/fail evidence for a layout task — no coder run, no
vision, no committed screenshots.

## Decisions (resolved 2026-11-23)

| Decision | Choice |
| --- | --- |
| Contract location | a **separate `specs/product/<spec>/layout.toml`** per spec |
| Control identity | **stable `data-testid`, kebab-case** (`origin-input`, `dest-input`, `start-walk`, `comfort-legend`, `top-card`, `sidebar`, `drawer`, `map`, `sidebar-handle`, `drawer-handle`) |
| Overlap | **siblings/peers only** — a button inside its card may overlap its ancestor |
| Failure | **gates**: an AC FAIL that queues the `T<n>` fix task (043 path) |
| Viewports | **desktop 1280×800 + mobile 390×844** |
| States | **initial no-route page AND route-planned** (fixtures) |
| Visibility | rendered, non-zero rect, in the page's normal scroll flow — not required above the fold |
| Flexible region | a control may list **candidate regions**; the check uses the one visible at that viewport (sidebar desktop / drawer mobile) |
| Rollout | **040 first**, backfill other product specs later |
| `data-testid` edits | **a product-spec task the swarm implements** (app change; not a harness direct edit) |

## Design

### Intermediate representation: `layout.toml`

Source-agnostic; the seam a future **Figma importer** feeds. Selectors are
`data-testid`-based, which is exactly what a Figma layer-name → testid mapping
needs.

```toml
[region.top-card]   # region ids are the layer names a Figma frame would use
selector = "[data-testid='top-card']"
anchor   = "top"
[region.map]
selector = "[data-testid='map']"
[region.sidebar]
selector = "[data-testid='sidebar']"
[region.drawer]
selector = "[data-testid='drawer']"

[control.origin-input]
selector = "[data-testid='origin-input']"
regions  = ["top-card"]              # candidate regions
[control.dest-input]
selector = "[data-testid='dest-input']"
regions  = ["top-card"]
[control.start-walk]
selector = "[data-testid='start-walk']"
regions  = ["sidebar", "drawer"]     # whichever is visible at this viewport
unique   = true
[control.comfort-legend]
selector = "[data-testid='comfort-legend']"
regions  = ["top-card", "sidebar", "drawer"]

[expect.desktop]
visible_regions = ["top-card", "map", "sidebar"]
hidden_regions  = ["drawer"]
[expect.mobile]
visible_regions = ["top-card", "map", "drawer"]
hidden_regions  = ["sidebar"]

[tolerance]
px        = 2        # border/scrollbar slack
overlap   = 0        # peer overlap allowed, in px
```

### Check kinds (deterministic, DOM-only)

One `layout_facts` snapshot per (viewport × state): `getBoundingClientRect()` +
visibility for every region and control, plus the peer-relationship map.

| Kind | Assertion |
| --- | --- |
| `present` | control exists **and** is visible (rendered, non-zero rect, in scroll flow) |
| `unique` | exactly one visible match (`offsetParent`-aware), for controls flagged `unique` |
| `in_region` | the control's rect is contained in one of its candidate regions' rects (± `tolerance.px`) |
| `region_visible` / `region_hidden` | per-viewport region expectation (sidebar vs drawer) |
| `region_order` | one region entirely above/left of another (top card above map) |
| `no_overlap` | no two **peer** interactive controls intersect beyond `tolerance.overlap` (ancestor/descendant excluded) |
| `no_overflow` | `scrollWidth <= clientWidth + tolerance.px` |

All checks read only `layout_facts`; the vision model is never consulted.

### Where it runs

Inside the existing acceptance runner: it already sets the two viewports, the
fixture backend, the geolocation mock, and the per-spec `acceptance.toml` pass.
Add the state transition (initial → route-planned) for the one spec under check,
a geometry fact collector, and the kinds above. A failing check is a normal
`Check` result, so 043's `queue_fix_tasks` appends the `T<n>` fix task naming the
control/region and the assertion.

## Non-goals

- No pixel/screenshot baselines, no diffing, no `toHaveScreenshot` (the Leaflet
  tile pane is network-rendered and would diff every run).
- No vision in the pass/fail path (it stays advisory).
- No Figma API/plugin now — only the IR + the `data-testid` naming it will target.
- No coder task for verification: this makes verification harness-owned.

## Acceptance criteria

- [ ] **AC-1 — presence.** Every declared control is `present` + `unique` (where
  flagged) on its declared viewport × state; a missing/duplicate/zero-size
  control fails, naming the control.
- [ ] **AC-2 — region containment.** Every control's rect is inside one of its
  candidate regions (± tolerance); a control outside fails with both rects.
- [ ] **AC-3 — region layout.** Per viewport, `region_visible`/`region_hidden`
  hold (desktop: sidebar, no drawer; mobile: drawer, no sidebar), `region_order`
  holds (top card above map), and `no_overlap`/`no_overflow` pass.
- [ ] **AC-4 — deterministic gate.** Runs on the two states with no screenshot,
  no vision, no network beyond the fixture backend; same DOM → same verdict; a
  failure gates (spec verdict FAIL) and queues the `T<n>` fix task.
- [ ] **AC-5 — Figma seam.** The IR is source-agnostic: a test proves a
  `layout.toml` generated from a Figma-shaped fixture (layer names → `data-testid`)
  drives the same checks with no engine change.
- [ ] **AC-6 — no regression.** `make test`, `make e2e`, `make swarm-test` green;
  the existing advisory probes/vision are unchanged.

## Files

- `specs/product/040-google-maps-layout/layout.toml` — the first contract.
- `specs/product/040-google-maps-layout/tasks.md` — **T22**: add the `data-testid`
  attributes to the Svelte components (swarm implements).
- `frontend/scripts/acceptance.mjs` — geometry fact collector + the check kinds.
- `swarm/acceptance.py` — parse `layout.toml`, map failures to fix tasks.
- `swarm/tests/test_acceptance.py` — a test per kind + the Figma seam.
