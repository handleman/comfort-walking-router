# 053 Swarm Hardening (2026-11-25) — Plan

References `specs/harness/053-swarm-hardening-2026-11-25/spec.md` AC-1–AC-6.

## Approach

Five small, independently testable changes. Each has a reproduction from the
2026-11-25 run records, so each test is a regression test with a real shape.
Order: grounding (biggest cost) → delta rule → per-task scope → e2e launch →
caps/health.

## Steps

1. **Grounded block (AC-1).** In the reviewer's verdict handling, after
   `judge_verdict`, if the verdict is `blocked`:
   - collect the recorded gates (`state.gates`) and the verifier verdict;
   - if every gate is `0` and the verifier is not blocked, require the block text
     to cite a concrete signal (a failing gate command, `exit=[1-9]`, a
     `file:line`, a `FAILED`/`test_` token, or an `AC-n`) *that is actually
     present in the evidence*;
   - otherwise set `state.ungrounded_block = True` and stop — no fix round.
2. **Reference vs required (AC-2).** Extend the delta guard's named-path
   extraction: a backtick path in a clause whose verb is `read|use|using|from|via|
   see|import` is a *reference*, not a required change. Only a path in an
   ownership clause (`edit|change|add|remove|create|write|update`) is required.
   Reuse the 030 `_READ_VERBS` machinery; add `use/from/via/see`.
3. **Per-task allowlist (AC-3).** Derive `task_paths(brief, plan_text)` = the
   backtick paths the brief/plan own (ownership verbs) plus the task's
   `artifacts.step_target` set. Before commit, revert any delta path outside it
   (recorded under `out_of_scope_reverted`). `e2e_required(brief, changed)` checks
   the *allowlist*, not the raw delta.
4. **Launch classification (AC-4).** In `swarm/e2e.py`, wrap the suite run so a
   spawn/launch exception yields `{"ran": False, "error": "..."}`. In
   `e2e_triage.classify`, an unrun suite is class `env` with the error; "ran but
   no parseable failures" stays `unclassified` with that distinction in the
   record.
5. **Caps + health (AC-5).** Raise `inner.MAX_TASKS` (or batch the roster in
   `write_roster`), and add `swarm/health.py` + `make swarm-health` that runs
   `pytest -q` and `npm --prefix frontend run test:e2e`, printing a table and
   exiting non-zero on failure.
6. **Tests (AC-6).** One test per AC using fixture shapes from the session
   (green gates + blocked verdict; brief naming an implemented helper; off-scope
   `frontend/e2e` write on a map task; a spawn `ENOENT`; an 11-failure roster).

## Risks

| Risk | Mitigation |
| --- | --- |
| Grounding too strict → real blocks stop | only fires when *all* gates are green AND the verifier passed; a cited failure still proceeds |
| Reference rule lets a needed file slip | ownership verbs still require it; the plan's step targets are always required |
| Per-task scope reverts legitimate edits | the allowlist includes the brief's ownership paths + plan step targets; global scope still applies |
| Health check is slow | it is opt-in (`make swarm-health`), not in the hot path |

## Rollback

Each step is a guarded branch; revert the commit to restore today's behaviour.
`SWARM_MAX_INNER_TASKS` stays an env override either way.
