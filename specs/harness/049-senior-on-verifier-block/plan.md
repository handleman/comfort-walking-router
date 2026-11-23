# 049 Senior Escalation on Verifier Block — Plan

References `specs/harness/049-senior-on-verifier-block/spec.md` AC-1–AC-6.

## Approach

One bounded insert in the flow's end-of-dev-loop, reusing the existing senior
crew and the verifier's already-rendered report. No new crew, no new flag.

## Steps

1. **Locate** the single place the blocked verdict is finalised: after the dev
   loop (`if _gates_green(gates) or dev_attempts >= DEV_ATTEMPTS: break`) and
   before the senior/gates-green determination. Today `verifier.blocked` short-
   circuits straight to the status mapping (`flow.py:4066`).
2. **Insert the escalation** (guarded by `verifier.blocked` and a new
   `senior_on_block` not-yet-run flag):
   - build `report` = `state.verifier["report"]` or joined `findings`,
   - `_kickoff(build_senior_crew(spec_dir, task, report, note), role="senior:verify", step="senior-block")`,
   - `self.state.senior_used = True`, `senior_rounds += 1`, note `senior_escalation_on_block`.
3. **Re-verify**: `if self._verify_phase(task, kick):` → clear the block and fall
   through to the existing green path (re-run `_review` + `_gates_or_evidence`
   on the new delta so a real green can be committed). Else keep `blocked`.
4. **Bound**: the escalation runs at most once per flow attempt (guard flag),
   independent of `SENIOR_ATTEMPTS`.
5. **Tests** (fixture, no LLM): stub `_verify_phase`/`_kickoff`/`build_senior_crew`
   to assert the two branches in AC-6 and that `senior_rounds` never exceeds 1.
6. **Verify**: `make swarm-test`, `ruff`, `mypy` green; run a real parked case
   (`make swarm-run SPEC=040 TASK=T16`) and confirm `senior_used: true` + a
   senior round + re-verify.

## Risks

| Risk | Mitigation |
| --- | --- |
| Senior fix regresses a green build | The existing `_verify_phase` self-check / correction guard still applies; re-verify re-reads the tree |
| A permanently-blocking verifier now costs 1 senior call per attempt | Bounded to one round; 3 supervisor attempts ⇒ at most 3 senior calls, all on the cheapest escalation model path |
| Interacting with the "unstable/stalled/overridden" verifier states | Escalate only when `blocked` is true (not `overridden`/`unstable`/`stalled`), so QA's authority is unchanged |

## Rollback

The insert is a single guarded block; reverting the commit restores the
gate-on-`not blocked` behaviour exactly.
