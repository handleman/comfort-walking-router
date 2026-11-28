# 041 Figma Redesign — Spec

Status: implemented — **operator-written accepted exception** (2026-11-28).
All seven tasks were completed outside the queue and recorded manually. This is
the one accepted exception: future app/UI/e2e work goes through
`specs/product/` and the queue, with the 90% visual gate and `covered_by`.
The design cache is synced; frames are scoped.

## What / Why

Replace the app's visual layer with the supplied Figma design while keeping every
behaviour and acceptance criterion intact. The three frames are the source of
truth for layout, colour, type, spacing and component states; the existing specs
remain the source of truth for behaviour. The design is a calm, green walking
app: a desktop top nav + left planning panel over a full-bleed map, and a mobile
map with a floating endpoint card, a results sheet and a full-height comfort
preferences sheet.

The design is **adapted**, not copied blindly: the design's `mellow.walk` brand,
the extra-walking-time slider, the second route card and the map layer pills are
not implemented because the product is Comfort Walking Router and the API has
no detour budget, no route alternatives and no layer data. The full transcription
and every deviation are in [`design-spec.md`](design-spec.md).

## Inputs

- **File:** `https://www.figma.com/design/jFwR8VpN5Nls2RjN2Ifh4y/budgetery`
  (key `jFwR8VpN5Nls2RjN2Ifh4y`, synced version `2424384819566238682`).
- **Frames** (allowlisted in `swarm.yaml`):
  - Desktop · Your walk — `6:61` (1440×900)
  - Mobile · Your walk — `6:53` (390×844)
  - Mobile · Comfort preferences — `6:57` (390×844)
- **Cache:** `designs/jFwR8VpN5Nls2RjN2Ifh4y/` (IR, renders, brief, lock).
- **Tokens:** `design-spec.md` §Tokens; checked by `design.toml`.
- **Breakpoints:** desktop 1280×800 (acceptance), mobile 390×844.

## Scope

- `frontend/src/App.svelte` — the responsive shell, the nav/panel, the mobile
  sheets and the map overlays.
- `frontend/src/app.css` — tokens and the Inter font.
- `frontend/src/lib/components/*` — the endpoint card, the comfort panel, the
  route summary, the mobile results/preferences sheets, the saved-walks and
  how-it-works dialogs.
- `frontend/src/lib/map/material.ts` — the additional Material icons.
- `frontend/e2e/*` — selectors updated to the new controls (same behaviours).
- `app/main.py` (+ `tests/`) — one narrow API widening: accept the scoring
  module's existing `balanced` preference so the design's "Balanced" segment is
  honest. No routing or scoring change.

## Non-goals

- New product behaviour: route alternatives, a detour/extra-time budget, map
  shade/noise layers. These get their own specs.
- Changing the brand to `mellow.walk`; the product stays Comfort Walking Router.
- Replacing Leaflet, the routing provider or the comfort scoring.
- Pixel diffing the design's mock browser chrome or its map tiles.
- Dark mode or a tablet breakpoint.

## Acceptance Criteria

- [ ] AC-1: **Brand and tokens.** The design's colours, type scale, spacing and
  radii are CSS custom properties (`--cwr-*`), Inter is self-hosted, the nav
  carries "Comfort Walking Router" + "A nicer way to get there.", and
  `design.toml` token checks are green.
- [ ] AC-2: **Desktop frame.** At 1280×800 the app renders the 72 px top nav,
  the 380 px left planning panel (endpoint card, comfort panel, route card,
  pinned CTA) over a full-bleed map with locate/zoom controls, the comfort
  legend and attribution; the sidebar edge handle still works.
- [ ] AC-3: **Mobile frames.** At 390×844 the app renders the floating endpoint
  card, the weather chip, the bottom results sheet ("Your kind of walk") and
  the 604 px "Walk your way" comfort sheet, with no horizontal overflow and the
  map visible above the sheet.
- [ ] AC-4: **Preferences and map controls.** More shade/Balanced/More sun
  persist as `hot`/`balanced`/`cloudy`, Quieter streets persists as
  `avoid_traffic`, Reset restores the defaults, changes re-plan when both
  endpoints are set, Saved walks and How it works open their dialogs, and the
  new controls are keyboard accessible with visible focus.
- [ ] AC-5: **Behaviour preserved and verified.** Route → summary → walk →
  saved routes still work; the 001–040 e2e hooks and layout regions resolve;
  `pytest`, `ruff`, `mypy`, the frontend check/lint/unit gates, the e2e suite
  and `make swarm-accept --strict` are green, with desktop and mobile
  screenshots attached.

## Design contract

- `design.toml` — tokens + region bounds (desktop frame `6:61`).
- `acceptance.toml` — a deterministic browser check per AC.
- `design-spec.md` — the exact transcription (copy, sizes, states, deviations).

## Queued work

`tasks.md` holds six tasks (T1–T6) plus a verification task (T7). They are
ordered so the app stays runnable: shell → desktop panel → desktop routes →
mobile results → mobile preferences → map/nav actions → verification. The
operator runs the queue with `SWARM_ACCEPT=0` and then the final acceptance pass,
because a partial redesign cannot satisfy every AC after each task.

## Open questions

- Route alternatives + detour budget (the design's second card and slider) are
  queued as a follow-up product spec after 041 lands.
- Map shade/noise layers are a follow-up; the legend key is text-only for now.
