# 016 Conflict Recovery — Spec

**Status: done 2026-11-10**

Control-plane spec: it changes `swarm/` and must stay in `HARNESS_SPECS`, so the
queue never tries to implement it.

## What / Why

The merge queue (`012 T18`) commits each green task on `swarm/<spec>-<task>`,
pushes it, then `--no-ff` merges into the base branch. A conflicting merge is
aborted and reported as `merge_failed` — correct, but terminal: the task's work
sits on a branch and a human has to merge it by hand.

On 2026-11-10 a *stash pop* (not a merge) conflicted and left `UU` stages in the
tree for three runs (fixed deterministically: preflight blocks unmerged paths,
restore resolves to `--ours`). That incident is **not** a job for an LLM.

A real branch conflict is different: two green deltas touched the same lines and
both sides are wanted. That is a code merge, and it is a good fit for one
dedicated crew that runs only then.

## Requirements

- **AC-1 — only on a real merge conflict.** The resolver runs after
  `git merge --no-ff` fails with unmerged paths, and never for `stash_conflict`,
  preflight failures, or red gates.
- **AC-2 — deterministic acceptance.** The merge is committed only when no
  conflict marker remains in the conflicted files, the crew edited **only**
  those files, **and** every configured gate (`gate_commands()`) exits 0. Otherwise the merge is aborted, the base is left
  untouched, and the run stays `merge_failed` with `autocommit.conflict`
  evidence (paths + reason).
- **AC-3 — one role, configurable, no gate tool.** A single
  `Merge Conflict Resolver` agent with read/edit tools only (no `ShellTool`), so
  it cannot run gates (015 D1). Model: `SWARM_CONFLICT_MODEL`, defaulting to
  `SWARM_CODER_MODEL`; `SWARM_<ROLE>_FALLBACK_MODEL`/`SWARM_LOCAL_FALLBACK_MODEL`
  apply like every other role. `SWARM_CONFLICT_CREW=0` disables the attempt.
- **AC-4 — auditable.** Usage is recorded under role `conflict` in
  `run.json usage.by_role`, and `autocommit` records `conflict` (paths + note),
  `merge` (`ok (crew resolved: …)` or `conflict: …`), and the gate outcomes.
- **AC-5 — bounded.** At most one resolver attempt per merge; no retry loop, no
  extra fix rounds. A failed attempt must not leave markers or `UU` stages.
- **AC-6 — stash conflicts stay deterministic.** No crew for a conflicted
  `git stash pop`; the restore resolves to `--ours` and records
  `stash_conflict` (already implemented).
- **AC-7 — no stash needs a human.** `swarm-*` stashes never accumulate as loose
  entries: at kickoff every orphan is archived as
  `refs/swarm/archive/<timestamp>-<sha>`, indexed in
  `swarm/runs/orphan_stashes.json`, and dropped; a conflicted restore archives
  the kept stash the same way and records `stash_conflict_ref`. Content stays
  readable with `git show <ref>:<path>`, a user's non-`swarm-*` stash is never
  touched, and `SWARM_ARCHIVE_STASHES=0` disables the lifecycle.

## Non-goals

- Resolving semantic disagreements about requirements (needs a human/spec edit).
- Replacing QA for task work: this crew only merges two already-green deltas.
- Rewriting history or force-pushing branches.
