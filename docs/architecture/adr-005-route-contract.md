# ADR-005: Route Contract — JSON Schema as Source of Truth

## Context
Backend (FastAPI) and frontend (Svelte + TS) share `POST /route` across stages 001, 007 (reroute requery), and 008 (provider swap). Contract drift would break all three. See ADR-003 (boundary), `specs/001-example-app/plan.md` step 1.

## Decision
- `contracts/route.json` (JSON Schema) is the source of truth; request/response types are generated or hand-mirrored from it on both sides.
- Geometry: GeoJSON (`LineString` per route leg) — Leaflet-native, no decode step.
- Preference: closed enum (`hot` | `cloudy`); unknown values rejected with 422, not defaulted.
- Errors: `{ code, message }` envelope on 4xx/5xx; frontend renders `message` verbatim for user-facing cases (e.g. off-route requery failure in 007).
- Additive changes only without a minor contract version bump; breaking changes need a new ADR.

## Alternatives Considered
- Encoded polyline: compact — rejected (decode step on both sides, worse debuggability for learning repo).
- Informal dict-shaped JSON: fastest — rejected (drift across 001/007/008, untestable).
- Full OpenAPI codegen: robust — deferred (overhead for MVP; JSON Schema + hand-mirrored TS types suffice).

## Consequences
- T1 scaffold must land `contracts/route.json` first; backend and frontend conform to it (AC coverage in 001, reused by 007/008).
- 008 provider swap must preserve the contract byte-for-shape (its AC-1 enforces this).
