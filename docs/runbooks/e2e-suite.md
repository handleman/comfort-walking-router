# Browser e2e suite runbook

`make e2e` builds the frontend, then runs `npx playwright test` from `frontend/`,
where `frontend/playwright.config.ts` boots the fixture backend
(`ROUTE_FIXTURES=1`) and `vite preview` itself.

```bash
make e2e   # build + fixture backend + playwright test
```

Last run: **12 passed** (2026-11-16).

## Fixtures mode

`ROUTE_FIXTURES=1` switches the backend to recorded responses — geocode, route
geometry and the OSM corridor come from committed fixtures — so the browser
scenarios are deterministic and never call a live provider.

## Why it is evidence

The 026 run-guards rule: a task whose delta touches `frontend/e2e/*` is green
only with a recorded Playwright run (`e2e_missing` otherwise). The suite is that
evidence — the harness records the execution in the run's `shell_log.jsonl` and
derives green from it, never from a model's claim. `swarm.evidence` matches
the exact argv (`npm --prefix frontend run build`, then
`npm --prefix frontend run test:e2e`).

## Limits

The suite is not a regression oracle for live providers (the fixtures pin the
answers); `test-results/` is gitignored; the three `preferences` specs need the
local Postgres (they skip without it).

Ran while writing: `make e2e` — 12 passed.
