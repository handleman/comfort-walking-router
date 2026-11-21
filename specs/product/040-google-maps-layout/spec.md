# 040 Google-Maps Layout — Spec

Product spec (the comfort route guide). Supersedes 036's 3-step flow; reuses its
Tailwind foundation (036-T1, green).

> **Status: being refined for clarity (the UI restructure is in progress).**

## Problem

Manual QA: the current sidebar UI is the wrong shape for a map app. The reference
is **Google Maps**: the map is the app, and controls are floating overlays or a
collapsed sheet. Today the map shares the screen with a fixed sidebar, Start/End
sit in that sidebar, config and saved routes are always visible, and the app
defaults to a hardcoded Munich centre instead of the user's position.

## Goal (unambiguous, per the confirmed behaviours)

The layout is **responsive** — one rule decides where the controls live:

| | Mobile (< 768px) | Desktop (≥ 768px) |
| --- | --- | --- |
| **Map** | full-bleed, fills the viewport | full-bleed, fills the viewport |
| **Sidebar** | **absent** | **present** (a fixed right/left panel) |
| **Controls** | a collapsed **bottom drawer** | the **sidebar** |
| **Top card** | floating over the map top | floating over the map top |

1. **Full-bleed map** on every screen size (the map fills the viewport; the
   sidebar on desktop overlays/sits beside it — it does not push the map into a
   small box).
2. **Floating top card** — a white rounded card over the top of the map with an
   **origin** row (blue my-location dot + "My location") and a **destination**
   row (red pin + the address), a drag-handle divider, and `⋯`/`↑↓` action
   icons. This is the ONLY form (no duplicate elsewhere).
3. **Controls** — **sidebar on desktop only**, **collapsed bottom drawer on
   mobile**. Both hold the same content: the route summary, Preferences and
   Saved routes, and the action buttons. The drawer is collapsed by default and
   expands like Google Maps'.
4. **Geolocation is the default start** — the origin row shows the current
   position and the map centres on it.
5. **Material SVG icons** — every glyph is an inlined Material Symbols SVG from
   https://fonts.google.com/icons.

## Scope

- `frontend/src/App.svelte` — responsive layout (full-bleed map; sidebar on
  desktop only; drawer on mobile), the floating top card, and the geolocation
  default start.
- `frontend/src/lib/components/TopSearchCard.svelte` — the two-field floating card.
- `frontend/src/lib/components/BottomDrawer.svelte` — the mobile collapsed drawer.
- `frontend/src/lib/map/material.ts` — inlined Material Symbols SVG paths.

## Non-goals

- Changing the backend, the API contract, or the walk/comfort logic.
- A custom router or new pages (single-page app).
- Third-party map SDKs (Leaflet stays).
- A transport-mode selector (car/transit/plane) — this is a walking app; the
  drawer shows the walk summary only.

## Acceptance criteria

- **AC-1 — Full-bleed map.** The map fills the viewport at every size; the
  sidebar (desktop) overlays it, it does not shrink it into a small box.
- **AC-2 — Floating top card.** The origin/destination fields render as one
  card over the map top (origin = my-location dot + "My location", destination =
  red pin), with a drag-handle divider and `⋯`/`↑↓` actions — the ONLY form.
- **AC-3 — Responsive shell.** The sidebar is rendered **only** on desktop
  (≥768px) and a bottom drawer **only** on mobile (<768px); on mobile the map
  is the only main surface. Never both at once.
- **AC-4 — Controls content.** The sidebar and the drawer each hold the route
  summary (duration · distance · arrival · terrain), Preferences, Saved routes
  and the action buttons; the drawer is collapsed by default. No transport-mode
  selector.
- **AC-5 — Geolocation default start.** With location granted, the origin shows
  the current position and the map centres on it.
- **AC-6 — Material icons.** All glyphs use inlined Material Symbols SVGs.
- **AC-7 — No regression.** `make e2e`, `npm run check`, `npm test` stay green;
  the e2e hooks (`.comfort-band`, `.comfort-legend`, `button.walk-start`, the
  search input) still resolve.

## Success definition

On a phone: a full-screen map with your location as the start, a floating field
at the top for the destination, and a collapsed bottom drawer for the route
summary and controls. On desktop: the same map and top card with the controls in
a side panel. Exactly the Google Maps ergonomics.
