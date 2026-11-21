# 040 Google-Maps Layout — Plan

## Layout (responsive — one rule)

```
MOBILE (<768)                       DESKTOP (≥768)
┌─────────────────┐                 ┌────────────────────────────┐
│ ┌─────────────┐ │                 │ ┌─────────────┐ ┌────────┐│
│ │● My loc  ⋯  │ │                 │ │● My loc  ⋯  │ │        ││
│ │⋮⋮⋮          │ │                 │ │⋮⋮⋮          │ │ SIDE-  ││
│ │📍 Dest    ↑↓ │ │                 │ │📍 Dest    ↑↓ │ │ BAR    ││
│ └─────────────┘ │                 │ └─────────────┘ │controls││
│                 │                 │                 │+prefs  ││
│   MAP (full)    │                 │   MAP (full)    │+saved  ││
│                 │                 │                 │+buttons││
│ ═══ drawer ════ │                 │ └────────────────────────┘│
│ (collapsed)     │                 └────────────────────────────┘
└─────────────────┘
```

## Steps

1. **Responsive shell.** In `App.svelte`, make `#map` full-viewport and make the
   layout responsive: the **sidebar is rendered only on desktop (≥768px)** and
   the **bottom drawer only on mobile (<768px)**. On mobile the map is the only
   main surface (no sidebar column).
2. **Floating top card.** `TopSearchCard.svelte` — origin (my-location dot) +
   destination (red pin) rows, drag-handle divider, `⋯`/`↑↓` actions — over the
   map top. This is the ONLY form (remove the old `<form>` from wherever it is).
3. **Controls content.** `BottomDrawer.svelte` (mobile) and the sidebar (desktop)
   render the same content: route summary (duration · distance · arrival ·
   terrain), Preferences, Saved routes, action buttons. Drawer collapsed by
   default.
4. **Geolocation default start.** First fix → centre the map + pre-fill the
   origin with the current position.
5. **Material icons.** `frontend/src/lib/map/material.ts` with inlined Material
   Symbols SVGs; replace the Bootstrap glyph and A/B pins.
6. **Verify.** `make e2e`, `npm run check`, `npm test`.

## Risks

- **e2e hooks** — keep the search input placeholder and `button.walk-start` /
  `.comfort-band` / `.comfort-legend` selectors.
- **Responsive via media query** — the sidebar/drawer switch is CSS + a mount
  check; do not render both at once.
- **No duplicate form** — the top card is the only form; nothing else renders
  Start/End inputs.
