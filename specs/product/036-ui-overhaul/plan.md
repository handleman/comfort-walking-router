# 036 UI Overhaul — Plan

## Shape

```
┌─────────────────────────────┐   ┌───────────────────────────┐
│  STEP 1 · Plan              │   │                           │
│  Start  [⌖ use my location] │   │         map               │
│  End    [⌖ pick on map]     │   │      (full-bleed)         │
│  Preference ▾  Manual ▢     │   │                           │
│            [Find route]     │   │                           │
├─────────────────────────────┤   │                           │
│  STEP 2 · Review (on route) │   │                           │
│  stats · comfort score      │   │                           │
│  legend · segments · factors│   │                           │
│            [Save]  [Start]  │   │                           │
├─────────────────────────────┤   │                           │
│  STEP 3 · Walk              │   │                           │
│  live position · reroute    │   │                           │
│  arrival                    │   │                           │
├─────────────────────────────┤   │                           │
│ ▸ Preferences  ▸ Saved routes│  │   (collapsed by default)  │
└─────────────────────────────┘   └───────────────────────────┘
```

## Steps

1. **Foundation (library decision).** Add Tailwind CSS v4 + shadcn-svelte and
   its `button`, `card`, `collapsible`/`accordion`, `select`, `checkbox`
   primitives; keep the comfort-band colours and the Leaflet map untouched.
   (Fallback: hand-rolled CSS tokens + the same primitive structure, no Tailwind.)
2. **Stepper shell.** Extract the three steps from `App.svelte`: Plan (the form),
   Review (the `{#if route}` block), Walk (WalkControls + arrival). One `Step`
   component with a `currentStep` state; the route result advances Plan → Review,
   "Start walk" advances Review → Walk.
3. **Collapse the secondary panels.** Preferences and Saved routes become
   collapsible sections closed by default, opened in place. `loadSaved`/`loadPrefs`
   still run on mount so a saved route recall can jump straight to Review.
4. **Inline location.** Move "use my location" into the Start field's row (a
   locate button/icon beside the input), and keep the "pick on map" (⌖) buttons
   as they are. Remove the standalone locate notice.
5. **Responsive.** Below a breakpoint (~768 px) the sidebar becomes a full-width
   panel/sheet at the bottom over the map; the map stays interactive behind it.
6. **Polish.** Apply the design tokens (spacing scale, type scale, radius,
   border/background colour) so the controls read as a designed UI (AC-5).

## Risks

- **Adopting Tailwind mid-project** touches every class; keep the refactor
  mechanical and run `npm run check` after each step so regressions surface
  early, not at the end.
- **The e2e selectors** (`button.walk-start`, `.comfort-band`, `.comfort-legend`,
  the search input) must keep their hooks; the restructure must not rename the
  elements the suite targets.
- **Svelte 5 runes** — the new primitives must be rune-native (shadcn-svelte is).
- **Mobile map + sheet** — the map's `locate`/`click` handlers must keep working
  while the sheet is open; the sheet should not swallow map taps.

## Measured acceptance

`make e2e` (12) green, `npm run check` clean, `npm test` (93) green, and the
three-step flow is reachable end-to-end from a fresh load.
