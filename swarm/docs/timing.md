# Phase timing and timeouts (022)

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Phase timing (022 T1)
`events.jsonl` is the only clock. Every crew records `crew_started`/`crew_done`
with the role the flow set around the kickoff, and `swarm/phases.py` pairs them
(a stack, so nesting is safe) into `run.json.phases`:
`{phase, started_at, ended_at, duration_seconds, failed, model}`. `make
swarm-report` prints p50/p90 per phase and the slowest one, so a 20-minute task
can be attributed to the call that ate it. No second timer, no second write path.

## Wall budget (022 T2)
`SWARM_TASK_WALL_BUDGET` (default 1800 s, `0` disables) is checked **between
phases and before every retry** — never mid-call, so a running generation
finishes and the budget decides. On breach the run stops as `needs_human` with
`reason_code=wall_budget`, `run.json.wall_budget_note` and `human_log.txt`
naming the phase and the elapsed/total (`qa: 901s of 900s`). The run record is
written, so `make swarm-replay` gets a row instead of a timeout.

## Timeout economics (022 T3)
`SWARM_LLM_FIX_TIMEOUT_SECONDS` (default 180) applies to fix, self-check, senior
and verifier crews; chat-like planner/QA calls keep `SWARM_LLM_TIMEOUT_SECONDS`
(default 90). A timed-out call is its own event (`llm_timeout`), retries are
counted in `run.json.retries`, and a retry is only started after the wall budget
check (T2) — so a 90 s timeout cannot quietly double the task.

## Concurrent verification (022 T4)
`SWARM_VERIFY_CONCURRENT=1` (default `0`) runs the **first, read-only** 019
verifier pass beside the first QA round:
- formatting runs *before* the thread starts, so no file changes while the
  verifier reads; the verifier runs no gate and writes nothing;
- both must pass for green;
- if the concurrent pass blocks, its corrections run **after** QA and the
  scenario is re-verified sequentially — a correction must never write while QA
  is running gates;
- roles are thread-local and usage comes from each crew's own `token_usage`, so
  the two phases stay attributed correctly; event writes are serialised.

`=0` restores the 021 order (verify, then QA). The flag ships on only if T6
measures a wall-clock win with no green loss.

## Lean verifier path (022 T5)
`SWARM_VERIFY_LEAN=1` (default `0`) skips the scenario verifier only when the run
delta is **docs-only and small**: every changed path under `docs/` or ending
`.md`, at most `SWARM_LEAN_MAX_PATHS` (4) paths and `SWARM_LEAN_MAX_LINES` (200)
changed lines, with all gates green. Test files are deliberately **not**
low-risk — a test with the wrong expectation is the 014-T7 class the verifier
exists for — and implementation paths always verify. The decision is recorded as
`verifier.verdict=skipped` + `skipped_reason`, so a skipped check is visible.

## 022 knobs
| Knob | Default | Effect |
| --- | --- | --- |
| `SWARM_TASK_WALL_BUDGET` | `1800` | per-task wall clock, checked between phases and before retries (`0` off) |
| `SWARM_LLM_FIX_TIMEOUT_SECONDS` | `180` | timeout for fix/self-check/senior/verifier calls (planner/QA keep `SWARM_LLM_TIMEOUT_SECONDS`) |
| `SWARM_VERIFY_CONCURRENT` | `0` | first read-only verifier pass runs beside QA (A/B) |
| `SWARM_VERIFY_LEAN` | `0` | skip the verifier for a docs-only small delta (A/B) |
| `SWARM_LEAN_MAX_PATHS` / `SWARM_LEAN_MAX_LINES` | `4` / `200` | the lean-path bound |
