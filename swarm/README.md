# Swarm harness — usage

A free-first CrewAI swarm that implements `specs/product/` tasks one at a time
(`specs/harness/009-swarm-harness/`, hardened by `specs/harness/012-dark-factory-harness/` and the
run guards of `specs/harness/026-run-guards/`). Each phase is a small crew with its own
model role; a CrewAI Flow (`swarm/flow.py`) sequences them and owns every
decision that must not be made by a model — retries, scope, green, commit.
Green comes from gate exit codes queued by QA, never from a model's prose; the
verifier, self-check and correction crews run under their own roles so their
executions can never count as gate evidence.

New here? Read [`docs/how-it-works.md`](docs/how-it-works.md) first: the role
table, the phase order, one flow diagram and the invariant behind it.

## Run
```bash
make swarm-run                 # foreground pilot (no args = resume; or ./swarm/run.sh 001 T1)
make swarm-local               # all-local pilot: Ollama Qwen for every role (overrides cloud .env)
make swarm-dash                 # dashboard attached to the current pilot
make swarm-up                   # pilot in background + dashboard attached
make swarm-up-local             # all-local pilot in background + dashboard attached
make swarm-test                 # harness unit tests (no LLM, no network)
make swarm-preflight            # validate models/keys/Ollama/venvs/gates (no LLM call)
make e2e                        # browser suite: build + fixture backend + playwright test
make swarm-record SPEC=014 TASK=T11  # standard trailers for a task finished by hand
make swarm-approve             # grant approval for the last checkpoint task (or SPEC=001 TASK=T3)
make swarm-approve SPEC=001 TASK=T3  # grant approval for a specific held task
make swarm-coder-image          # build tuned coder image (swarm/ollama/Modelfile → swarm-coder:latest)
```

## Documentation

`docs/` holds one file per topic. The short version: read `how-it-works.md`
once, then jump to what you need.

- [`docs/how-it-works.md`](docs/how-it-works.md) — roles, phase order, the flow diagram, the invariant.
- [`docs/setup.md`](docs/setup.md) — venv, model tiers/routing, preflight, coder image.
- [`docs/running.md`](docs/running.md) — dashboard, resume rules, escalation, event listener.
- [`docs/queue.md`](docs/queue.md) — how tasks are found, reopened, and added.
- [`docs/tools-and-gates.md`](docs/tools-and-gates.md) — guarded tools and who owns gate evidence.
- [`docs/verifier.md`](docs/verifier.md) — the read-only scenario check.
- [`docs/run-guards.md`](docs/run-guards.md) — the deterministic stops and their off switches.
- [`docs/e2e-self-heal.md`](docs/e2e-self-heal.md) — a red suite is triaged, repaired in-scope, and never weakened.
- [`docs/usage-and-budgets.md`](docs/usage-and-budgets.md) — tokens, cost, caps.
- [`docs/unattended.md`](docs/unattended.md) — overnight runs, tuning, stashes, supervisor.
- [`docs/risk-classes.md`](docs/risk-classes.md) — the risk label and the escape rate.
- [`docs/commits.md`](docs/commits.md) — merge queue, ledger, approval resume, sandbox.
- [`docs/parallel.md`](docs/parallel.md) — parallel attempts in worktrees.
- [`docs/testing.md`](docs/testing.md) — harness tests, browser suite, replay sets.
- [`docs/context-economics.md`](docs/context-economics.md) — prompts, compaction, gate selection, caching.
- [`docs/fix-loop.md`](docs/fix-loop.md) — tests-first, repair budget, telemetry, anti-loop guards.
- [`docs/timing.md`](docs/timing.md) — phase timing, wall budget, timeouts, concurrency.
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — traces and what each stop means.
