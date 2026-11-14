# 026 Run Guards — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [ ] T1 (AC-1, AC-2): `swarm/guards.py` with `empty_delta` and `missing_brief_files` (brief paths minus pre-existing files); in `swarm/flow.py` stop before the verifier as `no_delta` / `delta_incomplete`, record `run.json.delta_guard`, honour `SWARM_DELTA_GUARD=0`; tests for empty, partial and complete deltas.
- [ ] T2 (AC-3): one fail-closed helper in `swarm/guards.py` (parse → one repair → terminal) and wire it to the verifier, QA and senior verdict paths in `swarm/flow.py`; tests that `unknown` never returns green.
- [ ] T3 (AC-4): in `swarm/flow.py::_verify_phase`, capture the static-check result before the correction steps and after each one; on a green→red transition revert that correction's files (archive first), record `verifier.correction_reverted`, end the loop; `SWARM_CORRECTION_GUARD=0`; tests with a fake correction that breaks a check.
- [ ] T4 (AC-5): per-provider quota counter in `swarm/flow.py` (third quota error → `_QuotaExhausted`), `llms.fallback_model` returns only callable models, `run.json.quota`; `swarm/preflight.py` 1-token probe per role (skipped by `--offline`); tests for the breaker and the empty chain.
- [ ] T5 (AC-6): every `Agent` in `swarm/crew.py` gets `max_retry_limit=0`; test that one outage produces one call per harness attempt, not a nested retry storm.
- [ ] T6 (AC-7): `swarm/usage.py` + `swarm/flow.py` set `usage.cost_unknown` and a budget note naming the unpriced model; dashboard shows `unknown` not `$0`; tests for two paid models and for an unpriced model.
- [ ] T7 (AC-8): `swarm/evidence.py::e2e_executions` + `swarm/flow.py` require a Playwright execution when the brief names `frontend/e2e/*` (`e2e_missing`, `SWARM_E2E_EVIDENCE=0`); `Makefile` `e2e` target; preflight checks the binary and browser version; tests with and without a record.
- [ ] T8 (AC-9): ensure `run.json.error` and `human_log.txt` carry the `_ConfigError` text; `swarm/preflight.py` builds planner/coder/reviewer/senior/verifier with the same `allow_paid` flags as the crews; tests.
- [ ] T9 (AC-10): `swarm/done.py` returns a reason per entry and `swarm/flow.py` logs `open task <id>: <reason>` at queue selection; add `swarm/record.py` + `make swarm-record SPEC=… TASK=…` writing the standard trailers; tests for both.
- [ ] T11 (AC-12): wall budget is terminal — `swarm/bounded.py` accepts `float | None` (None = unbounded) and refuses a zero/negative timeout; `swarm/flow.py` raises `_WallBudget` before a call when `remaining <= 0`; regression test in `swarm/tests/test_bounded.py` (landed with the 007 2.7 h overrun fix).
- [ ] T10 (AC-11): add `026-run-guards` to `HARNESS_SPECS`; record the guards and off switches in `AGENTS.md`, `swarm/README.md`, `docs/roadmap.md`, `changelog.md`; `make swarm-test` green.

## Decisions

- **Guards are deterministic and stop, not fail.** Each writes a typed reason
  code and a `human_log.txt` line; none of them can turn a green run red, so
  they ship on by default (except AC-2's `delta_incomplete`, which starts as a
  stop and is promoted to a gate only after the replay set agrees).
- **The verifier stays the behaviour judge.** AC-1/AC-2 check presence; the
  verifier still checks that the scenario does what the brief says.
- **No autonomy widening.** Guards reduce escapes; they do not justify class 2.
