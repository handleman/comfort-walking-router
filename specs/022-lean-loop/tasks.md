# 022 Lean Loop — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [ ] T1 (AC-1): derive per-phase timing from `events.jsonl` into `run.json.phases` (phase, role, model, started_at, ended_at, duration_seconds) with no second clock, and add p50/p90 per phase plus the slowest-phase share to `make swarm-report`.
  Evidence: `swarm/flow.py`, `swarm/events.py`, `swarm/report.py`, `swarm/tests/test_phases.py`.
- [ ] T2 (AC-2): enforce `SWARM_TASK_WALL_BUDGET` (default 900 s, 0 off) between phases and before a retry; on breach stop as `needs_human` / `reason_code=wall_budget` with the phase and elapsed in `human_log.txt`, never mid-crew.
  Evidence: `swarm/flow.py`, `swarm/humanlog.py`, `swarm/tests/test_autoloop.py`.
- [ ] T3 (AC-5): split timeouts — `SWARM_LLM_FIX_TIMEOUT_SECONDS` (default 180) for fix/senior/verifier/correction crews, keep the chat timeout for planner/QA — and record `llm_timeout` events plus `run.json.retries`; skip a retry whose worst case cannot fit the remaining wall budget.
  Evidence: `swarm/llms.py`, `swarm/flow.py`, `swarm/tests/test_cache.py`, `swarm/tests/test_autoloop.py`.
- [ ] T4 (AC-3): run the 019 verifier and the first QA round concurrently when `SWARM_VERIFY_CONCURRENT=1` (default 0): read-only verifier, QA runs gates, both must pass, listener writes serialised by a lock, sequential fallback when off.
  Evidence: `swarm/flow.py`, `swarm/events.py`, `swarm/tests/test_concurrent_verify.py`.
- [ ] T5 (AC-4): add the lean verifier path — `SWARM_VERIFY_LEAN=1` (default 0) skips the scenario verifier only for a low-risk delta (docs/tests/mechanical under `SWARM_LEAN_MAX_LINES`/`SWARM_LEAN_MAX_PATHS`) with all gates green; record `verifier.skipped_reason`; implementation paths always verify.
  Evidence: `swarm/verify.py`, `swarm/flow.py`, `swarm/tests/test_verify_lean.py`.
- [ ] T6 (AC-6): run the outcome suite with the budget and the paid/fast pin for baseline, concurrent and lean arms; record green, wall clock, per-phase p50, retries and cost in `docs/research/fix-loop-2026.md`; targets p50 ≤ 10 min for a two-file case and ≤ 45 min for five cases, green not lower than 021.
  Evidence: `docs/research/fix-loop-2026.md` (results), `swarm/bench/replay_baseline.json`.
- [ ] T7 (AC-6): keep concurrency and the lean path only on a measured wall-clock win with no green loss; otherwise revert to the flag-off default and record the negative result.
  Evidence: `docs/research/fix-loop-2026.md`, `changelog.md`.
- [ ] T8 (AC-7, AC-8): close out — add `022-lean-loop` to `HARNESS_SPECS`, document every knob in `.env.example` and `swarm/README.md`, update `AGENTS.md`/`docs/roadmap.md`/`changelog.md`, and run `make swarm-test`, `ruff check .`, `mypy app tests`.
  Evidence: `swarm/flow.py::HARNESS_SPECS`, `.env.example`, `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`.

## Decisions (2026-11-14)

- **Latency before parallelism.** The paid bake-off showed the coder is capable
  (gate-green in ~5 min) while the loop spends 20+ minutes in sequential
  phases. Parallel **tasks** (023) multiply a latency that is still too high;
  first make one task finish predictably.
- **Concurrency is opt-in.** Running the verifier and QA together changes what
  can go wrong; both must pass, the listener is locked, and the A/B decides.
- **The lean path is a risk-class seed.** It is the smallest useful classifier
  (docs/tests/mechanical vs implementation) and 023 expands it to class 0–3.
- **The wall budget is not a gate.** It stops a run at a known point with a
  copyable reason; it cannot make a run green and does not change QA evidence.

## Phase 022 evidence

Four capped live runs of `007-live-position-T2` with a paid coder: two steps and
all six gates green in ~5 minutes, then 20+ minutes in fix/verdict/retry; the
local 9.7B QA hung ~9 minutes on one verdict. The loop is ~10 sequential phases
at 30–90 s each. Full account: `docs/research/fix-loop-2026.md`.
