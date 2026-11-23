# 050 Corridor Reliability Test Stand — Tasks

Each task maps to one acceptance criterion.

- [ ] T1 (AC-1): add `vcrpy` + `pytest-recording` to `requirements-dev.txt`; record a real Munich-corridor `[out:json]` response into `tests/cassettes/overpass_corridor.json`.
- [ ] T2 (AC-1): `tests/test_corridor_parse.py` — assert `shade_factor`, `quiet_factor`, `lit_share` and segment split from the cassette; runs `--record-mode=none --block-network`.
- [ ] T3 (AC-2): `tests/test_overpass_retry.py` — mock `requests.get` for the three-mirror order (`overpass-api.de` → `overpass.kumi.systems` → `overpass.private.coffee`), per-endpoint attempt log, timeout, 5xx, and "data gap, never 5xx".
- [ ] T4 (AC-3): `swarm/smoke.py` (or `swarm/corridor_check.py`) — `corridor-check` POSTs a fixed route against the three mirrors and reports corridor-present, segment count, serving mirror, per-mirror status/latency.
- [ ] T5 (AC-3): `Makefile` — `make corridor-check` target.
- [ ] T6 (AC-4): `frontend/e2e/geolocation.spec.ts` — allowed / denied (`clearPermissions`) / unavailable (`setGeolocation(null)`) / moved (`setGeolocation` mid-session); assert auto-centre/origin pre-fill and the denied fallback.
- [ ] T7 (AC-5): `make test`, `make e2e`, `make swarm-test`, `ruff check .`, `mypy app tests` green.
- [ ] T8 (AC-5): confirm cassettes/fixtures are secret-free (no live keys or tokens committed); note a nightly GitHub Action for `make corridor-check` as follow-up.
