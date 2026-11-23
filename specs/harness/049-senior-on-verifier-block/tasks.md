# 049 Senior Escalation on Verifier Block — Tasks

Each task maps to one acceptance criterion.

- [ ] T1 (AC-1): `swarm/flow.py` — after the dev loop, when `self.state.verifier.get("blocked")` and the senior-on-block guard is unset, run one `build_senior_crew` round (role `senior:verify`) before the status mapping.
- [ ] T2 (AC-2): `swarm/flow.py` — feed the senior round `state.verifier["report"]` (fallback: joined `findings`) + `state.verifier["note"]`.
- [ ] T3 (AC-3): `swarm/flow.py` — after the senior round, call `self._verify_phase(task, kick)`; if it passes, clear the block and fall through to QA/gates so the task can go green; if it still blocks, leave `blocked` true.
- [ ] T4 (AC-4): `swarm/flow.py` — a per-run guard (e.g. `senior_on_block`) so this path runs at most once per flow attempt.
- [ ] T5 (AC-5): `swarm/flow.py` — set `senior_used`, increment `senior_rounds`, and add a `verifier` note (`senior_escalation_on_block`) for the dashboard/report.
- [ ] T6 (AC-6): `swarm/tests/test_verify.py` — fixture tests: (a) block → one senior round → re-verify passes → green path; (b) block → one senior round → re-verify still blocked → `verifier_blocked`; assert `senior_rounds` never exceeds 1.
- [ ] T7 (AC-6): `make swarm-test`, `ruff check swarm/`, `mypy app tests` all green.
- [ ] T8 (verify): real run `make swarm-run SPEC=040 TASK=T16` shows `senior_used: true`, one senior round, a re-verify, and a green or honestly-still-blocked outcome.
