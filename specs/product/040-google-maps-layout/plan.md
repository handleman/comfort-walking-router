# 040 Google-Maps Layout — Plan

## Layout (responsive — one rule)

```
MOBILE (<768)                       DESKTOP (≥768)
┌─────────────────┐                 ┌────────────────────────────┐
│ ┌─────────────┐ │                 │ ┌─────────────┐ ┌────────┐│
│ │● My loc     │ │                 │ │● My loc     │ │      ││
│ │⋮⋮⋮          │ │                 │ │⋮⋮⋮          │ │ SIDE-││
│ │📍 Dest    ↑↓ │ │                 │ │📍 Dest    ↑↓ │ │ BAR  ││
│ └─────────────┘ │                 │ └─────────────┘ ║controls││
│                 │                 │                 ║+prefs ││
│   MAP (full)    │                 │   MAP (full)    ║+saved ││
│                 │                 │                 ║+btns  ││
│ ═══ drawer ════ │                 │                 ║handle ││
│ (collapsed)     │                 │                 └────────┘│
└─────────────────┘                 └────────────────────────────┘
```

The row marker icons (blue dot / red pin) are the map-pick triggers; the sidebar
collapses via a vertical edge handle (click), like Google Maps' drawer.

## Steps

1. **Responsive shell.** In `App.svelte`, make `#map` full-viewport and make the
   layout responsive: the **sidebar is rendered only on desktop (≥768px)** and
   the **bottom drawer only on mobile (<768px)**. On mobile the map is the only
   main surface (no sidebar column).
2. **Floating top card.** `TopSearchCard.svelte` — origin (my-location dot) +
   destination (red pin) rows, drag-handle divider, `↑↓` swap — over the map
   top. Row marker icons arm map-pick; no `⌖`/`⋯` buttons. This is the ONLY form
   (remove the old `<form>` from wherever it is).
3. **Controls content.** `BottomDrawer.svelte` (mobile) and the sidebar (desktop)
   render the same content: route summary (duration · distance · arrival ·
   terrain), Preferences, Saved routes, action buttons. Drawer collapsed by
   default; exactly one `WalkControls` (no duplicate section).
4. **Geolocation default start.** First fix → centre the map + pre-fill the
   origin with the current position (address, else coordinates). No fix →
   modal asking for the start location (text search or pick on map).
5. **Auto-plan.** Both endpoints set → `POST /route` automatically; swap of two
   set endpoints re-plans. No Find-route button.
6. **Material icons.** `frontend/src/lib/map/material.ts` with inlined Material
   Symbols SVGs; replace the Bootstrap glyph and A/B pins.
7. **Verify.** `make e2e`, `npm run check`, `npm test`.

## Risks

- **e2e hooks** — keep the search input placeholder and `button.walk-start` /
  `.comfort-band` / `.comfort-legend` selectors.
- **Responsive via media query** — the sidebar/drawer switch is CSS + a mount
  check; do not render both at once.
- **No duplicate form** — the top card is the only form; nothing else renders
  Start/End inputs.
- **No duplicate controls** — `WalkControls` is rendered only by
  `ControlsContent`; `App.svelte` must not render a second one.
- **Auto-plan loop guard** — only plan when both endpoints are set and the
  endpoint pair actually changed; a bare reactive statement can loop.
