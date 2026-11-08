# 004 Weather-Sun — Tasks

- [x] T1 (AC-1, AC-5): Open-Meteo client in `app/providers/open_meteo.py` (current temp + cloud at midpoint, timeout + User-Agent) with fixture tests in `tests/test_open_meteo.py`.
- [ ] T2 (AC-2): Auto-rule in `app/preferences.py` (constants: temp ≥25°C and cloud <70% → hot/shade; cloud ≥70% → cloudy/sun; else caller preference) with matrix tests in `tests/test_preferences.py`.
- [ ] T3 (AC-4): Weather cache in `app/weather_cache.py` (SQLite, ~30 min TTL, keyed by rounded midpoint) with tests in `tests/test_weather_cache.py`.
- [ ] T4 (AC-1, AC-4): Wire weather + auto-rule into `POST /route` in `app/main.py` with caller fallback on failure; add `applied_preference`, `preference_source`, `weather` to `contracts/route.json` and test in `tests/test_route_weather.py`.
- [ ] T5 (AC-3): Add the source chip (`Auto: …` / `Manual`) and manual-override toggle to `frontend/src/App.svelte`; keep `npm run check` green.
