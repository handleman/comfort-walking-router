# 024 Earned Autonomy — Plan

Status: implemented. References `specs/024-earned-autonomy/spec.md` AC-1–AC-7.

## Approach

One classifier, one decision function, one wiring point. The hold already exists
(012); this phase makes it consult a risk decision instead of a global switch.
Autonomy is off by default, so the change is inert until an operator opts in.

## T1 — risk ladder (`swarm/risk.py`)

- Path classes as in AC-1; unknown and empty are 3.
- Sensitive brief keywords (`auth`, `payment`, `migration`, `infra`, `secret`)
  force 3.
- `label()` for the record.

## T2 — decision

`decision()` takes the changed paths, brief, gates, verdict, verifier and the
knobs; returns the class, the inputs and `auto_merge` + `reason`. Every refusal
has a named reason so an operator can see why a low-risk run still held.

## T3 — wiring

In `save_run`'s green branch:
- build the decision from `changed`/`brief`/`state.gates`/verdict/verifier;
- `payload["autonomy"] = decision`;
- the hold condition becomes
  `self._require_approval and not approved and not decision["auto_merge"]`.
The commit path is unchanged: an auto-merged run still creates the branch,
merges through the queue, writes the trailers and pushes.

## T4 — telemetry

- `human_log.txt`: `risk class N (label): auto-merged|human merge — reason`.
- `make swarm-report`: runs per class + the auto-merged count.
- The record is the input for a future escape-rate ratio (reverts/hotfixes per
  auto-merged class); measuring escapes is a separate step.

## T5 — tests

Ladder cases, sensitive briefs, every decision branch, the source wiring and the
two views. No model, no git.

## T6 — docs and controls

`HARNESS_SPECS += ("024-earned-autonomy",)`, `.env.example`, `swarm/README.md`,
`AGENTS.md`, `docs/roadmap.md`, `changelog.md`; the live measurement is recorded
as not evaluated until a green baseline exists.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A docs change hides a behaviour change | class is path-based; `app/`, `frontend/src/`, `contracts/` are class 2 |
| A test change encodes wrong behaviour | class 1 still requires the 019 verifier; tests-first evidence is the seed |
| Auto-merge bypasses QA | auto-merge only when QA gates are green and the verdict is pass; QA evidence is unchanged |
| Escape rate unknown | the decision record is emitted now; measurement is the next decision |
| Operator surprise | default off; explicit `--require-approval` still holds |
