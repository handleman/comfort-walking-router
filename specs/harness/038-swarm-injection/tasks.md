# 038 Swarm Injection & Release — Tasks

- [ ] T1 (AC-1): Introduce `swarm.yaml` and route `scope`, `gates`, `risk`, `specs_dir`, and the target root through it (defaults byte-equal to today's `DEFAULT_SCOPE`/`SWARM_GATE_COMMANDS`/`HARNESS_SPECS`), so the harness runs unchanged from a config file.
- [ ] T2 (AC-2): Delete every `app/`, `frontend/`, `tests/`, `contracts/` string from the swarm core (tools_guarded, risk, prompts, evidence, preflight); everything product-shaped comes from `swarm.yaml`.
- [ ] T3 (AC-3): Split the repos — move `swarm/` into its own package/repo and leave the product in place; `swarm init` in the product repo writes `swarm.yaml` + `.swarm/`.
- [ ] T4 (AC-3): Move the product-specific drivers (smoke, e2e, db, Overpass/Mapbox/Postgres) out of core into the product repo behind `swarm.yaml` gates.
- [ ] T5 (AC-4): Package it — `swarm` console script, `pyproject.toml`, semver tags, GitHub release + PyPI publish, `swarm init` pins a release, `swarm --version`.
- [ ] T6 (AC-5): Migrate the comfort-route-guide onto the packaged swarm and keep `make test`, `make e2e`, `make swarm-test` green.
