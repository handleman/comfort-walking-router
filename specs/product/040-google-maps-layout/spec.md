# 040 Google-Maps Layout — Spec

Product spec (the comfort route guide). Supersedes 036's 3-step flow; reuses its
Tailwind foundation (036-T1, green).

## Problem

Manual QA: the sidebar UI — and the in-progress 3-step flow — is the wrong shape
for a map app. The reference is **Google Maps**: the map is the app, and every
control is a floating overlay or a collapsed drawer. Today the map shares the
screen with a fixed sidebar, Start/End sit in that sidebar, config and saved
routes are always visible, and the app defaults to a hardcoded Munich centre
instead of the user's position.

## Goal (the Google-Maps layout, per the attached screenshots)

1. **Full-bleed map** — the map fills the whole viewport on every screen size.
2. **Floating top card** — a white rounded card overlaying the top of the map
   with two fields: an **origin** row (a blue "my location" dot + a placeholder
   like "My location") and a **destination** row (a red pin + the address),
   separated by a divider with a vertical drag-handle, and action icons on the
   right (a `⋯` menu and an `↑↓` swap).
3. **Bottom drawer** — a white rounded-top sheet over the map bottom, with a
   centered grab-handle pill at the top, a header (mode label + filter/share/
   close `×` icons), a **transport-mode selector** (car / transit / walk / plane
   chips with durations), a **route summary** (duration · arrival · distance ·
   terrain note), and **action buttons** (Go / Add stops / Navigate). Collapsed
   by default, expands like Google Maps'.
4. **Geolocation is the default start** — the origin row shows the current
   position ("My location") and the map centres on it, instead of a hardcoded
   default.
5. **Material SVG icons** — every glyph (my-location dot, red pin, swap, menu,
   filter, share, close, walk, the transport-mode icons) is an inlined Material
   Symbols SVG from https://fonts.google.com/icons, not the Bootstrap glyph or a
   text fallback.

## Scope

- `frontend/src/App.svelte` — full-bleed map + floating top card + bottom drawer.
- `frontend/src/lib/components/` — `BottomDrawer.svelte` (grab handle + header +
  slots) and a `TopSearchCard.svelte` (the two-field floating card).
- `frontend/src/lib/map/material.ts` — inlined Material Symbols SVG paths
  (24×24, `fill="currentColor"`); `frontend/src/lib/map/icons.ts` reuses them
  for the map pins.
- Geolocation: pre-fill the origin row + centre on the first fix.

## Non-goals

- Changing the backend, the API contract, or the walk/comfort logic.
- A custom router or new pages (single-page app).
- Third-party map SDKs (Leaflet stays).

## Acceptance criteria

- **AC-1 — Full-bleed map.** The Leaflet map spans the full viewport; no fixed
  sidebar column remains.
- **AC-2 — Floating top card.** The origin/destination fields render as a card
  over the top of the map (two rows, divider with a drag handle, `⋯`/`↑↓`
  actions); the map stays interactive behind it.
- **AC-3 — Bottom drawer.** A grab-handle drawer over the map bottom holds the
  header (mode + filter/share/close), a transport-mode selector, a route
  summary, and the action buttons; collapsed by default, expands in place.
- **AC-4 — Geolocation default start.** With location granted, the origin shows
  the current position and the map centres on it.
- **AC-5 — Material icons.** All glyphs use inlined Material Symbols SVGs.
- **AC-6 — No regression.** `make e2e`, `npm run check`, `npm test` stay green;
  the e2e hooks (`.comfort-band`, `.comfort-legend`, `button.walk-start`, the
  search input) still resolve.

## Success definition

A phone user opens the app to a full-screen map with their location as the
starting point, types an end address into the floating field at the top, and
expands a collapsed bottom drawer only when they need the route summary,
preferences or a saved route — exactly the Google Maps ergonomics in the
screenshots.
