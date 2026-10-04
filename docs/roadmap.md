# Roadmap

## 0 — Foundations (done)
- Constitution with quality gates, mission (comfort-first walks), stack: Python + FastAPI + Svelte + TypeScript + Leaflet, OSM/Overpass, SQLite cache first.

## 1 — 001 MVP: comfort-scored walk (next)
- Svelte + Leaflet map: enter start/end → scored route + why-explanation.
- FastAPI scoring API over OSM data; factors: shade + sun + quiet.
- SQLite cache for OSM responses. Verify: `pytest` + `ruff` + `mypy` + `npm run check`, demo route renders.
- Spec: `specs/001-example-app/spec.md` → plan → tasks → implement.

## 2 — Spec milestones (each its own `specs/NNN-*/`, ADR if cross-cutting)
- `002-map-ux`: Svelte + TS inputs (start/end, hot/cloudy toggle), Leaflet route + explanation panel, loading/error/empty states. Accept: toggle flips preference, errors readable, `npm run check` clean.
- `003-cache-perf`: SQLite cache keying + TTL + cache-hit metric; debounce + timeouts on routing/geodata providers. Accept: repeat query skips externals, slow-backend degrades gracefully.
- `004-weather-sun`: real weather-aware sun preference (hot/cloudy auto + manual override). Accept: sunny-hot prefers shade, overcast prefers sun, override respected.
- `005-saved-routes`: Postgres for saved routes/prefs (+ accounts if needed). Accept: save/recall route, prefs persist; needs ADR (storage switch).
- `006-comfort-plus`: richer factors (surface, lighting, safety/traffic). Accept: each factor toggled + explained, no MVP regression.
- `007-live-position` (spec drafted): walk-mode marker, no voiceover. Sim + GPS providers, snap + sustained-drift (>30 m, ~10 s/3 fixes) tap-to-reroute warning, auto-center toggle, arrival banner + Stop. No auto-rerouting.
- `008-mapbox-routing` (spec drafted, post-MVP): swap OSRM interim → Mapbox free tier behind provider interface. Accept: contract unchanged, token backend-only, cache-hit skips Mapbox, no live calls in tests.

## 3 — Non-goals (no spec yet)
- Turn-by-turn, mobile native, offline maps.
