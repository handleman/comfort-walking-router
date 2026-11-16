# 025 Durable Journal — Plan

Status: implemented (first slice). References `specs/025-durable-journal/spec.md`
AC-1–AC-6 and `docs/architecture/adr-012-orchestration-stance.md`.

## Approach

Add the kernel beside the existing records; do not replace them.

```
journal.py  events (idempotent key) + steps (leases) + effects + fold
     │
     ├─ flow: run_started, seed_steps, complete_step
     ├─ resume: completed_outputs if longer than progress.json
     ├─ commit: effect key (run, delta) around _commit_changes
     └─ run.json.journal = fold(run)
```

## T1 — store

SQLite WAL; one writer. `events` has `UNIQUE(run_id, key)` with `key` nullable
so non-idempotent notes are allowed; `steps` is `(run_id, idx)`; `effects` is
keyed by a stable string.

## T2 — leases

`claim_step` is one atomic UPDATE (`status != 'done'` and a free/expired lease);
`heartbeat` only for the owner; expiry uses wall time (a lease is coordination,
not measurement).

## T3 — resume

`complete_step` stores the digest and the last 2000 chars of output in the event.
The flow merges `journal.completed_outputs` with the checkpoint outputs and takes
the longer prefix; the recovery note says `journal` when it does.

## T4 — effects

`_commit_green` computes `commit:<run>:<delta-signature>`, returns the recorded
result when present, otherwise commits and records it. This is the first real
effect; merge/push/approval follow the same shape when they need it.

## T5 — projection and docs

`run.json.journal` = `{status, events, steps, effects}`. `HARNESS_SPECS`,
`AGENTS.md`, `docs/roadmap.md`, `changelog.md`; the limits (no dispatcher, no
concurrent workers, SQLite) are recorded next to ADR-012's triggers.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A second authority disagrees with `run.json` | the journal owns steps/effects; `run.json` is the fold/view and is derived, never edited independently |
| A stale lease blocks a step | TTL + atomic claim; single-machine pilot has one writer |
| An effect key hides a real re-commit | the key includes the delta signature; a different delta is a different key |
| SQLite contention | WAL + one writer; Postgres is the ADR trigger for real workers |
