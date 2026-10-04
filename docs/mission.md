# Mission

Learn the full spec-driven loop (spec → plan → tasks → implement) by building a comfort-first walking router — "Google Maps for walks".

## Problem
Shortest routes are often unpleasant: sun on hot days, traffic noise, no greenery. Walkers want the most comfortable route, not the shortest.

## Users
- Primary: self-use (dogfood the SDD loop on own walks).
- Secondary: general city walkers with the same comfort needs.

## MVP (specs/001-example-app)
Minimal web map: enter start/end → get comfort-scored route + short explanation (why this route).
Comfort factors v1: shade + sun + quiet (from OSM tags: tree cover/parks, orientation/weather-aware sun preference, traffic avoidance). Greenery included under shade. No accounts, no saved history.

## Non-goals (MVP)
- No native/mobile app, no turn-by-turn navigation.
- No live weather station integration; simple hot/cloudy preference toggle only.
- No Postgres yet; no user accounts.

## Done means
1. `specs/001-*/spec.md → plan.md → tasks.md` exists with checkboxes linked to spec items.
2. Minimal FastAPI + Leaflet map renders a scored route from OSM data with tests passing.
3. Each spec item verified via `pytest + ruff + mypy` per constitution.
