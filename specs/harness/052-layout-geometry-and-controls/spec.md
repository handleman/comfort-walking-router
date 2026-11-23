# 052 Layout Geometry & Control Presence — Spec

Harness spec (control plane; the queue never runs it).

## Problem

Layout verification today is **advisory and ad-hoc**:

- the acceptance pass (`frontend/scripts/acceptance.mjs`, 043) drives Playwright,
  but its per-AC probes are hand-written `exists / absent / count / min_count /
  text / value_set / route_request` checks in `acceptance.toml`, plus a handful
  of global facts (`zeroSize`, `overflow`, `duplicateButtons`, `tiles`, `leaflet`,
  `consoleErrors`);
- a vision model adds a second opinion, but it is non-deterministic and cannot
  gate a commit;
- there is **no geometry**: nothing asserts that a control sits in the region it
  belongs to, that regions tile the viewport, or that interactive controls do not
  overlap;
- the expected-control list is scattered across specs, so "the sidebar has the
  handles it should" is only checked where someone remembered to write a probe.

Consequence: a layout task (040 `T6`-class, "verify the layout") is a
*meta-verification* task the coder cannot satisfy by writing code — it parks as
`e2e_unclassified` because the required evidence is a recorded Playwright run the
coder never produced. Verification must be **harness-owned and deterministic**.

## Goal

A deterministic, screenshot-free verification of two things, per viewport:

1. **Control presence** — every control the layout promises exists, is visible
   (non-zero rect, inside the viewport), and is unique where it should be unique.
2. **Basic geometry** — each control sits inside its declared **region**; regions
   tile the viewport as declared (top card above the map, sidebar on one side on
   desktop, drawer at the bottom on mobile, never both); interactive controls do
   not overlap; no horizontal overflow.

The same checks are the pass/fail evidence for a layout task — no coder run, no
vision, no committed screenshots.

## Design

### Intermediate representation: the layout contract

A small, source-agnostic model the check engine consumes. It is the seam that
lets a **Figma importer** feed the same checks later.

```toml
# specs/product/<spec>/layout.toml  (or a [layout] block in acceptance.toml)
[region.top_card]
selector = ".top-search-card"
anchor   = "top"
[region.map]
selector = "#map"
[region.sidebar]
selector = "aside.sidebar"
[region.drawer]
selector = ".bottom-drawer"

[control.origin_input]
selector = "input[placeholder='e.g. Marienplatz, Munich']"
region   = "top_card"
role     = "textbox"
[control.dest_input]
selector = "input[placeholder='e.g. Englischer Garten']"
region   = "top_card"
[control.start_walk]
selector = "button.walk-start"
region   = "controls"        # whichever of sidebar/drawer owns controls
unique   = true
[control.comfort_legend]
selector = ".comfort-legend"
region   = "controls"

[expect.desktop]
visible_regions = ["top_card", "map", "sidebar"]
hidden_regions  = ["drawer"]
[expect.mobile]
visible_regions = ["top_card", "map", "drawer"]
hidden_regions  = ["sidebar"]
```

### Check kinds the engine adds (deterministic, DOM-only)

Collected once per viewport from `getBoundingClientRect()` for every region and
control (plus `offsetParent`/`visibility`/`opacity` for "visible"):

| Kind | Assertion |
| --- | --- |
| `present` | control exists **and** is visible (non-zero width/height, in viewport) |
| `unique` | exactly one visible match (no duplicate control) |
| `in_region` | the control's rect is contained in its region's rect (with a small tolerance) |
| `region_visible` / `region_hidden` | per-viewport region expectation (sidebar vs drawer) |
| `no_overlap` | no two interactive controls' rects intersect beyond a tolerance |
| `region_order` | one region is entirely above/left of another (top card above map) |
| `no_overflow` | `scrollWidth <= clientWidth + tolerance` (already a global fact; now a check) |

All thresholds explicit (e.g. `tolerance_px = 2`, `overlap_max_px = 0`),
so a flaky 1px border never fails a run.

### Where it runs

Inside the existing acceptance runner (`acceptance.mjs` already sets desktop +
mobile viewports and evaluates DOM), so it shares the fixture backend, the
geolocation mock, and the per-spec `acceptance.toml` pass. New geometry facts are
added to the same JSON the vision step reads; failures become the same `T<n>`
fix tasks 043 already queues. **The check path itself is DOM-only** — the vision
model stays advisory and is never consulted for pass/fail.

### Figma, in future (design seam, not this spec)

A Figma frame is, in this model, the same three things: **regions** (frames /
groups), **controls** (named layers), and **per-viewport expectations**. A future
importer maps Figma layer names → selectors (via `data-testid` / role / label)
and emits the same `layout.toml` IR, so the check engine is unchanged. This spec
only establishes the IR and the selector-mapping convention (`control.selector`
resolved from a stable `data-testid`), and records the mapping table as the
Figma contract to be filled by that importer.

## Non-goals

- No pixel/screenshot baselines, no diffing, no `toHaveScreenshot` (rejected for
  this app: the Leaflet tile pane is network-rendered and would diff every run).
- No vision in the pass/fail path (it stays advisory).
- No Figma API/plugin implementation now — only the IR + selector convention it
  will target.
- No change to the coder's task list; this makes verification harness-owned, it
  does not add coder work.

## Acceptance criteria

- [ ] **AC-1 — presence.** Every declared control is asserted `present` +
  `unique` (where flagged) on its declared viewports; a missing/duplicate/zero-size
  control fails with the control name.
- [ ] **AC-2 — region containment.** Every control's rect is inside its declared
  region (± tolerance); a control outside its region fails with both rects.
- [ ] **AC-3 — region layout.** Per-viewport `region_visible`/`region_hidden`
  hold (desktop: sidebar, no drawer; mobile: drawer, no sidebar) and
  `region_order` holds (top card above map); `no_overlap` and `no_overflow` pass.
- [ ] **AC-4 — deterministic gate.** The checks run with no screenshot, no vision
  and no network beyond the fixture backend; the same DOM gives the same verdict.
- [ ] **AC-5 — queues fixes.** A failure becomes an `acceptance.toml`-driven
  `T<n>` fix task (043 path) naming the control/region and the failing assertion.
- [ ] **AC-6 — Figma seam.** The IR is source-agnostic: a single test proves a
  `layout.toml` generated from a Figma-shaped fixture (layer names → selectors)
  drives the same checks with no engine change.
- [ ] **AC-7 — no regression.** `make test`, `make e2e`, `make swarm-test` green;
  the existing advisory probes/vision are unchanged.

## Files

- `specs/product/<spec>/layout.toml` — the IR (starting with 040).
- `frontend/scripts/acceptance.mjs` — geometry fact collector + the check kinds.
- `swarm/acceptance.py` — parse the IR, map failures to fix tasks; `CHECK_KINDS`.
- `swarm/tests/test_acceptance.py` — fixture tests for each kind + the Figma
  seam (AC-6).
