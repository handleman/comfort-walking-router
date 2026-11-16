# Verification runbook

One line per target on what it proves, and an honest list of what nothing here
proves.

| Command | Proves |
| --- | --- |
| `make test` | 214 pytest — the app's unit/integration behaviour (route contract, comfort scoring, the saved-routes DB paths). |
| `make lint` | `ruff check .` — style and the enabled static rules, app + swarm. |
| `make typecheck` | `mypy app tests` — type safety of the backend. |
| `make swarm-test` | 724 harness unit tests — the swarm's deterministic logic (queue, guards, prompts, ledger). |
| `make e2e` | 12 Playwright — the user scenarios in a real browser, against fixtures. |
| `make smoke-live` | One real Munich route through the live providers (Mapbox + Overpass + weather). |
| `make swarm-preflight` | Models, keys, venvs and gate binaries are usable before the first LLM call. |

## What this does not prove

- **Replay convergence.** `make swarm-replay` runs the frozen green corpus; it
  was 2/5 green (40%) before the 033 planner change and is re-measured in
  `changelog.md`.
- **Escape rate.** `make swarm-report` joins green commits with `This reverts …`
  and reports 0/68 (0%). That is a floor: a hand-fixed regression is not
  counted, and the window is short.
- **The real-GPS walk** (007 AC-8) and **looking at the live map** (001 AC-2)
  are human gates; `make smoke-live` is the code half, a person is the other.
- **Product judgement.** A green run is gate evidence (exit codes recorded in
  `shell_log.jsonl`), not a statement that the feature is good.

Commands verified in the `Makefile` while writing; `make smoke-live` exists and
was verified 2026-11-15.
