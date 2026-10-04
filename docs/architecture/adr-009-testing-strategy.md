# ADR-009: Testing Strategy — Fixtures, No Live Externals in CI

## Context
Every stage touches paid/quota external APIs (Mapbox, Open-Meteo) or policy-sensitive ones (OSRM demo, Overpass, Nominatim). CI must be deterministic, fast, and quota-free, while one live smoke still validates reality. See 001/004/007/008 plans (all mandate fixture tests + off-CI smoke).

## Decision
- Recorded fixtures: every external client ships with a checked-in fixture response; unit/integration tests replay fixtures only — zero live calls in CI, enforced by no-network test config where practical.
- Determinism: sim-mode walk (007), scorer matrix (001/006), rule matrix (004) run on fixed inputs with exact assertions.
- Live smoke is manual and off-CI: one route per provider change (008), one weather fetch (004), one GPS walk (007); documented in tasks as T-final steps, never gating merge.
- Failure-path coverage mandatory: timeout, 429/quota, permission-denied, empty-result — each provider client tests its fallback (cache, manual default, sim fallback, clear message).

## Alternatives Considered
- Live sandbox in CI: most realistic — rejected (quota burn, flakiness, policy risk on every push).
- Mocks-only (hand-built): simple — rejected (drift from real shapes; recorded fixtures stay honest).
- No mandated smoke: pure CI — rejected (fixture staleness goes unnoticed; one manual smoke catches it).

## Consequences
- Fixture refresh is a maintenance task on provider-shape change; stale fixtures fail loudly against `contracts/route.json` validation (008 T4 pattern).
- Constitution P7 gates stay green without network; quota spend is bounded to manual smokes.
