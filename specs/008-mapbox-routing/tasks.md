# 008 Mapbox Routing — Tasks

- [ ] T1 (AC-1, AC-4): Add `app/providers/mapbox.py` implementing the existing `RouteProvider` interface (walking profile, 1–2 alternatives, timeout + single retry, GeoJSON `LineString` + distance/time) with recorded fixtures in `tests/fixtures/mapbox-*.json` and `tests/test_mapbox_provider.py` (no live calls).
- [ ] T2 (AC-2): Add `app/config.py` with a required `MAPBOX_TOKEN` accessor that raises a clear `RuntimeError` when missing/empty, with `tests/test_config.py`, and set a dummy token in `tests/conftest.py` so the suite stays hermetic.
- [ ] T3 (AC-3): Add calls-vs-cache-hits INFO logging around the route cache in `app/main.py` (cache hit skips the provider) with `tests/test_route_cache_logging.py`.
- [ ] T4 (AC-1): Construct and inject `MapboxProvider` from `app/config.py` in `app/main.py` (replace the OSRM instance), keep `contracts/route.json` unchanged, update `tests/test_route_api.py` to monkeypatch the provider, and add `tests/test_mapbox_contract.py` replaying a fixture through the scorer.

<!-- Human/infra gate, not queued (no code change): document `MAPBOX_TOKEN` in `.env.example` +
     `docs/tech-stack.md` (docs are outside coder scope) and run one manual live smoke off-CI to
     confirm quota + response shape. -->
