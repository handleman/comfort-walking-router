# 008 Mapbox Routing — Tasks

- [ ] T1 (AC-1, AC-4): Mapbox client (walking, alternatives, timeout+retry) behind scorer interface + fixture unit tests.
- [ ] T2 (AC-2): `MAPBOX_TOKEN` wiring (fail-fast, `.env.example`, gitignore, `tech-stack.md` note) per ADR-006.
- [ ] T3 (AC-3): Reuse SQLite cache; add calls-vs-hits quota logging.
- [ ] T4 (AC-1): Contract conformance test (recorded fixture → scorer → `contracts/route.json` validation); frontend untouched.
- [ ] T5 (AC-4): Green `pytest` + `ruff` + `mypy`; one manual live smoke off-CI.
