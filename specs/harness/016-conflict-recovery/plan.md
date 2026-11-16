# 016 Conflict Recovery — Plan

## Flow

```
_commit_changes (merge mode)
  ├─ git switch -c swarm/<spec>-<task>; add; commit; push branch
  ├─ git switch <base>
  ├─ git merge --no-ff <branch>
  │    rc == 0 → push base (existing path)
  │    rc != 0 → _unmerged_paths()
  │        ├─ [] → abort, merge_failed (unchanged)
  │        └─ conflict + resolver + SWARM_CONFLICT_CREW=1
  │              ├─ build_conflict_crew(paths) → one kickoff
  │              ├─ conflict_markers(paths) empty?
  │              ├─ gate_commands() all exit 0?
  │              ├─ yes → git add paths; git commit; push base
  │              └─ no  → git merge --abort; merge_failed + reason
```

## Pieces

| File | Change |
| --- | --- |
| `swarm/llms.py` | `conflict_llm()`: `SWARM_CONFLICT_MODEL` → `SWARM_CODER_MODEL`; per-role fallback |
| `swarm/crew.py` | `build_conflict_crew()`: read + edit tools only, one task, one agent |
| `swarm/flow.py` | `_commit_changes(..., resolver=...)`; `_resolve_conflict()`; `conflict_markers()`; `_run_gate_commands()`; record usage under `conflict` |
| `swarm/flow.py` | `HARNESS_SPECS += "016-conflict-recovery"` |
| `.env.example`, `swarm/README.md`, `changelog.md` | knobs + behaviour |
| `swarm/tests/test_conflict.py` | resolver wiring, abort path, marker check, no gate tool |

## Safety rules

- The resolver never sees the whole repo: prompt lists the conflicted files and
  the QA transcript tail; tools enforce `DEFAULT_SCOPE`.
- `git add` happens in the harness, after the marker check — the crew never
  stages or commits.
- Gates run in the base worktree with the same `SWARM_GATE_COMMANDS`; a failure
  aborts the merge, so `main` never carries a half-merged tree.
- One attempt. `SWARM_CONFLICT_CREW=0` restores the pre-016 behaviour exactly.

## Evidence

`run.json.autocommit` gains:

```json
{
  "conflict": "frontend/src/App.svelte — crew resolved; gates: 4/4 green",
  "merge": "ok (crew resolved: frontend/src/App.svelte)"
}
```

Failure keeps `ok: "0"`, `merge: "conflict: …"`, plus the reason.
