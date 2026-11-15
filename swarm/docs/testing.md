# Tests and evidence

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Unit tests (no LLM, no network)
```bash
swarm/.venv/bin/python -m pytest swarm/tests -v
```

## Browser e2e (`frontend/e2e`)
```bash
npm --prefix frontend run build
(cd frontend && npx playwright test)        # needs browsers: npx playwright install chromium
```
The Playwright config boots `uvicorn app.main:app` from the repo root with
`ROUTE_FIXTURES=1` and a placeholder `MAPBOX_TOKEN`, then `vite preview` on
:5173. `vite preview` does **not** inherit `server.proxy`, so `vite.config.ts`
carries an explicit `preview.proxy` for `/route`, `/geocode`, `/prefs`, `/saved`
and `/token`; without it the browser gets the SPA's 404 page ("Unexpected token
'<'") and no `.result` can render. Fixtures know the UI's Munich places
(`Marienplatz, Munich`, `Englischer Garten`) and build the route geometry from
the requested coordinates. Current state: 5/10 scenarios pass; walk mode is not
mounted in `App.svelte` (007-T10) and the prefs panel's select is the other
failure.

## Replay bench (`make swarm-bench`, 020 T1)
A frozen corpus of 12 historical green runs (`swarm/bench/corpus/*.json`) plus a
committed pre-change snapshot (`swarm/bench/baseline.json`). It measures the
size of what the harness sends, not what a model answers, so it runs in seconds
with no key and no network:

```bash
make swarm-bench             # table: task prompt chars, report chars, gates/round, Δ vs baseline
make swarm-bench-build       # rebuild the corpus from git trailers + run.json (deliberate)
make swarm-bench-baseline    # re-snapshot after a reviewed change
make swarm-bench ARGS="--json --case 006-comfort-plus-T3"
```

- A case pins the run id, the green SHA (and `base_sha = green_sha^`), the
  brief, the referenced AC paragraphs, the plan lines that name its files, the
  delta file contents with a SHA-256 each, the recorded gate results, a bounded
  gate transcript and a deterministic failing-round fixture for the report.
- `task_prompt_chars` estimates one replay: steps × step prompt + QA rounds × QA
  prompt + fix rounds × fix prompt + one verifier prompt. It is a stable proxy
  for tokens, not a bill; `run.json` stays the source of truth for real cost.
- A case is rejected when its green commit touches none of the files the brief
  names (014-T2: green without the endpoint). `007/T6`-style trailers are
  normalised to the spec directory, exactly like the done ledger.
- Exit codes: `1` = corpus missing or its digest no longer matches the baseline
  (rebuild and re-snapshot on purpose); `2` = the corpus could not be built.
- The bench never calls a model, never writes outside `swarm/bench/` and never
  mutates git. Prompt text is model-independent; crews are built with
  `ollama/bench` for the duration of a measurement.

## Live replay (`make swarm-bench-live`, 020 T7)
The offline bench measures prompts; only a real run shows whether the loop still
reaches green. `make swarm-bench-live CASE=006-comfort-plus-T3`:

1. refuses a dirty tree, a linked worktree, or a case without `base_sha`;
2. creates `git worktree add --detach <tmp> <green_sha^>`;
3. copies the **current** `swarm/` package into it (never `.venv`, `runs`,
   `__pycache__` or `bench/corpus`);
4. runs `python -m swarm.flow --spec <spec> --task <task> --no-commit --no-tui`
   with `PYTHONPATH=<tmp>`, `SWARM_BENCH=1` and the pinned models from
   `SWARM_BENCH_MODELS=coder=…,qa=…,planner=…,senior=…,verifier=…`;
5. reads that run's `run.json` and prints status, wall clock, prompt/cached
   tokens, cost, fix rounds and gates; the worktree is removed on success and
   kept (path printed) on failure.

It needs models and is never part of `make swarm-test`. Use a small case first;
`make swarm-bench ARGS=--list` shows the ids.

## Outcome replay suite (`make swarm-replay`, 021 T1)
`make swarm-bench` measures prompt text; the suite measures outcomes. It runs
each selected corpus case through the live path (worktree at `green_sha^`, current
harness, pinned models, no commit) and reports green, wall clock, prompt/cached
tokens, cost and fix rounds:

```bash
make swarm-replay                  # default 5 cases + delta vs replay_baseline.json
make swarm-replay-off              # same cases, every 021 knob at its 020 value
make swarm-replay-one CASE=004-weather-sun-T2   # one case, JSON details
python -m swarm.bench.replay --update-baseline  # snapshot the first run
```

- `SWARM_REPLAY_CASES=case,case` overrides the selection;
  `SWARM_REPLAY_TIMEOUT` (default 2400 s) or `--timeout` bounds one case.
- The suite is opt-in (models required, ~60 min for five cases) and never part of
  `make swarm-test`; the bookkeeping is tested with a fake runner.
- `swarm/bench/replay_baseline.json` stores the first run: case list, per-case
  status/time/tokens/fix rounds, the totals and the harness commit.
- `004-weather-sun-T2` is deliberately in the set: it is the case the 020 T8
  replay failed on (`verifier_blocked`), so it is the loop's current worst case.
