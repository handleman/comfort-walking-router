# 038 Swarm Injection & Release — Plan

## Shape

```
swarm-harness/  (package, versioned, app-agnostic)
  swarm/          -- crews, flow, guards, tools, prompts (no app strings)
  pyproject.toml  -- `swarm` console script
  swarm init      -- writes swarm.yaml + .swarm/ into the TARGET repo

comfort-route-guide/  (the target app repo)
  swarm.yaml      -- specs_dir, scope, gates, risk, e2e, db, models
  specs/ app/ frontend/ tests/ contracts/   -- the product
  .swarm/         -- runs, plans, journal, corpus (gitignored)
```

## Phases

1. **Extract the target contract.** Introduce `swarm.yaml` and route every
   hardcoded path through it: `DEFAULT_SCOPE` → `scope`, `risk.py` globs →
   `risk`, gate validators → `gates`, `specs_dir`/`HARNESS_SPECS` → `specs_dir`,
   `REPO_ROOT` → a `target` root passed at init. Keep the current values as the
   generated default so nothing breaks.
2. **Separate the repos.** Move `swarm/` (and its tests, bench, ollama models,
   scripts) into its own repo/package; leave `app/`, `frontend/`, `tests/`,
   `contracts/`, `specs/`, `docs/`, `Makefile` (app half) in the product repo.
   The product repo gets a `swarm.yaml` + a dev pin (`swarm init --dev .`).
3. **Move product-specific drivers out of core.** `swarm/smoke.py`,
   `swarm/e2e.py`, `swarm/db.sh`, and the Overpass/Mapbox/Postgres knowledge move
   to the product repo (as its own `tools/` or behind `swarm.yaml` gates/e2e);
   the swarm core keeps only the *generic* driver shapes (a gate runner, a
   report builder, a worktree integrator).
4. **CLI + packaging.** `swarm` console script (`swarm run|up|dash|preflight|
   report|init|--version`), `pyproject.toml`, semver tags, GitHub release +
   PyPI publish.
5. **Migrate + verify.** Point the comfort-route-guide at the packaged swarm and
   keep `make test`/`make e2e`/`make swarm-test` green; record the replay suite
   as the regression guard.

## Risks

- **Coupling is deep** (scope, gates, risk, prompts, smoke/e2e/db all name the
  app). Extract one axis at a time and keep `swarm.yaml` defaults byte-equal to
  today's values so each step is a no-op until the next.
- **Two repos, one history.** The split is a `git subtree`/`filter-repo` split;
  keep the product repo's history and move `swarm/` history via subtree so blame
  survives.
- **Replay/corpus** reference the app's files; they belong to the *product*
  repo (or a per-target corpus dir), not the swarm core.
- **No regression.** The whole point is reuse without losing the current green;
  `make swarm-test` + `make swarm-replay` are the guard on every phase.
