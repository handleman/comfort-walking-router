# 040 Google-Maps Layout — Plan

## Shape (from the screenshots)

```
┌─────────────────────────────────────┐
│  ┌─────────────────────────────────┐│
│  │ ●  My location            ⋯    ││   floating top card
│  │ ⋮⋮⋮  (drag-handle divider)     ││   (origin / destination rows)
│  │ 📍  Lenin Square           ↑↓  ││
│  └─────────────────────────────────┘│
│                                     │
│              MAP (full-bleed)       │
│                                     │
│  ┌─────────────────────────────────┐│
│  │        ▔  (grab handle)         ││
│  │  On foot            ⇅  ⤴  ✕    ││   bottom drawer
│  │  🚗  🚌  🚶10min  ✈             ││   (mode selector)
│  │  10 min · 700 m · arrival …     ││   (route summary)
│  │  [Go]  [Add stops]  [Navigate]  ││   (action buttons)
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

## Steps

1. **Full-bleed map + floating top card.** Make `#map` fixed/full-viewport. Build
   `TopSearchCard.svelte`: two rows (origin with the blue my-location dot +
   "My location" placeholder; destination with a red pin), a drag-handle divider
   between them, and `⋯`/`↑↓` action icons. Wire each row to the existing
   `SearchInput` so search still works.
2. **Bottom drawer.** Build `BottomDrawer.svelte` (grab-handle pill, header with
   mode label + filter/share/close icons, expandable). Put the route summary
   (duration · arrival · distance · terrain), a transport-mode selector
   (car/transit/walk/plane chips with durations) and the action buttons
   (Go / Add stops / Navigate) inside. Preferences and Saved routes move into
   this drawer. `loadSaved`/`loadPrefs` still run on mount.
3. **Geolocation default start.** On the first fix, centre the map and set the
   origin row to the current position (reverse-geocode it into the field); a
   manual entry overrides it.
4. **Material icons.** Add `frontend/src/lib/map/material.ts` with inlined
   Material Symbols SVG paths (24×24, `fill="currentColor"`) for the glyphs:
   `my_location`, `location_pin`/`place`, `swap_vert`, `more_horiz`, `tune`,
   `share`, `close`, `directions_walk`, `directions_car`, `directions_bus`,
   `flight`, `search`. Reuse them in the top card, the drawer and the map pins.
5. **Verify.** `make e2e`, `npm run check`, `npm test`.

## Risks

- **e2e hooks** target the search input and `button.walk-start`; the restructure
  must keep those selectors/labels or the suite breaks.
- **Overlays vs map taps** — the top card and drawer must not swallow map
  gestures in their empty space (pointer-events only on the interactive parts).
- **Reverse-geocode the origin** must not block first render; the field fills
  when the fix arrives, never before.
