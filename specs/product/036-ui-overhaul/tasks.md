# 036 UI Overhaul — Tasks

- [x] T1 (AC-5): Add Tailwind CSS v4 to `frontend/` — the Vite plugin in `frontend/vite.config.ts` and `@import "tailwindcss"` in `frontend/src/app.css` — and hand-roll three small primitives with Tailwind classes: `frontend/src/lib/components/ui/Button.svelte`, `frontend/src/lib/components/ui/Card.svelte`, `frontend/src/lib/components/ui/Collapsible.svelte`. Keep the Leaflet map and the comfort-band colours unchanged; `npm run build` and `npm run check` green. (Done, green.)

T2–T6 are **superseded by `specs/product/040-google-maps-layout/`**: the
Google-Maps layout (full-bleed map, floating top card, collapsed bottom drawer,
geolocation default start, Material icons) replaces this spec's 3-step flow and
covers the collapse / locate / responsive / verify work there. T1 (the Tailwind
foundation) is kept and reused.
