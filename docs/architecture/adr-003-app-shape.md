# ADR-003: App Shape — Monorepo with FastAPI + Svelte

## Context
MVP spans a Python scoring API and a Svelte map UI sharing one route contract. See `docs/tech-stack.md`, `specs/001-example-app/plan.md` (step 1: scaffold `app/` + `frontend/` + `contracts/route.json`).

## Decision
- Monorepo: `app/` (FastAPI, serves API + static frontend build), `frontend/` (Svelte + TypeScript + Leaflet via Vite), `contracts/route.json` (shared `POST /route` schema).
- Boundary: frontend never calls routing/geodata providers (OSRM interim, Mapbox in 008, OSM/Overpass) directly; all geodata via `POST /route`. Business logic in TS as pure functions; backend behind FastAPI `Depends` injection (constitution P8).
- Frontend build output served as static files by FastAPI; dev via `npm run dev` HMR + `uvicorn --reload`.

## Alternatives Considered
- Single Python SSR app (no Svelte): less tooling — rejected (poorer map interactivity for live-position stage).
- Separate repos/deployments: independent scaling — rejected (overhead for solo MVP; contract drift risk).
- Frontend-direct OSM calls: fewer backend hops — rejected (key/policy sprawl, duplicated caching, untestable scoring).

## Consequences
- One repo, one contract, clear test split (`pytest` backend, `npm run check` + unit tests frontend).
- Cost: Node/Vite build step required; keep component surface tiny per roadmap.
