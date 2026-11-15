# Usage, cost and budgets

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Usage, cost & budgets (012 T11/T14)
Every kickoff adds `CrewOutput.token_usage` to the run: prompt/completion/cached
tokens, LLM calls, and the models actually used. `run.json` gains:

```json
"usage": {"prompt_tokens": 8123, "completion_tokens": 640, "total_tokens": 8763,
          "llm_calls": 14, "models": ["ollama/swarm-coder:latest"],
          "cost_usd": 0.0, "started_at": "…", "finished_at": "…", "duration_seconds": 92.4}
```

Local Ollama and `:free` models are exactly `$0`. A paid model with a known rate
(`swarm/usage.py`) is estimated from tokens; an unknown paid rate reports
`cost_usd: null` / `cost=unknown` in the TUI instead of inventing a number.

Budgets are env-driven and stop the pilot with `budget_exhausted`:
`SWARM_MAX_TOKENS` (2M), `SWARM_MAX_COST_USD` ($3), `SWARM_MAX_RUNTIME_SECONDS`
(14400), plus per task `SWARM_MAX_COST_PER_TASK`/`SWARM_MAX_SECONDS_PER_TASK`.
Set any to `0` to disable it. `budget_note` records which limit tripped. The QA
review bypasses the cost cap — gates and the local reviewer are free, and a cap
must never turn into an unverified `needs_human`. **A local coder (`ollama/…`)
that has spent nothing is exempt from the cost/token and per-task caps** (its
spend is exactly $0); only the run-level time cap still applies. Three local
runs had stopped with `budget_exhausted` purely on the per-task 1800 s clock
(T9 2342 s, T10 2039 s, 005-T8 1885 s) while making progress. The exemption is
deliberately tied to `cost == 0`: with `SWARM_ALLOW_PAID=1` a paid planner or
senior still re-enables every cap, and an unknown price (`None`) is never
treated as free. `run.json budget.local_coder` / `budget.free_local_run` record
which rule applied.
