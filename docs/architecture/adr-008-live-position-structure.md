# ADR-008: Live-Position Frontend Structure (007)

## Context
007 puts GPS handling, snapping, drift detection, and reroute flow in the Svelte frontend. Without a structure rule this logic would tangle DOM/map concerns with testable math. See `specs/007-live-position/plan.md`, constitution P8 (reuse, KISS).

## Decision
- Pure-TS core in `frontend/src/lib/navigation/`: interpolate, snap-to-segment, drift detector, arrival check — zero DOM, zero Leaflet, zero `watchPosition` imports. Unit-tested directly.
- Thin shell: Svelte components own marker rendering, auto-center, warning banner, and provider wiring only; all decisions delegated to the core.
- Providers (`sim` | `gps`) expose one tick interface (`{ lat, lon, accuracy, t }`); GPS is an adapter over `watchPosition`, sim is deterministic playback. Shell never branches on provider type beyond setup/teardown.
- Reroute is a shell concern (calls `POST /route`, swaps the leg); drift *detection* stays in core.

## Alternatives Considered
- Logic in Svelte components: fastest — rejected (untestable without DOM/GPS mocks, un-reusable).
- Backend-owned snapping (POST position → GET snapped): consistent stack — rejected (per-fix latency, quota burn, offline-hostile; browser math suffices).
- Single provider abstraction with modes: fewer files — rejected (sim determinism vs GPS messiness deserve separate adapters).

## Consequences
- 007 T1/T2 follow this split; core stays portable if walk-mode ever moves (e.g. PWA, 006-style factor previews along legs).
- Leaflet objects never cross into core — enforced by import rule (core imports only GeoJSON types + math).
