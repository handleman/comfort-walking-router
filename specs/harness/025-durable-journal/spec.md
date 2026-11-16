# 025 Durable Journal — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

The harness recovers by *recording*: `events.jsonl` is telemetry, `progress.json`
is a per-step snapshot, and the done ledger lives in git trailers. None is an
authority. A crash between a step and its checkpoint re-runs the step; a
duplicate commit is prevented by inspection, not by an idempotency key. ADR-012
records the durable event-sourced orchestrator as an option with triggers; this
phase builds its first slice so the seams exist before 023 needs them.

## Goal

Make completed work and side effects durable and replayable **without** rewriting
the flow: an append-only journal is the authority for step completion and
effects, `run.json` stays the operator view, and nothing about green changes.

## Scope (option C, first slice)

- `swarm/journal.py`: SQLite (WAL) `events` (append-only, idempotent key),
  `steps` (status, attempt, lease), `effects` (idempotent side effects), and
  `fold(run_id)` as a projection.
- Flow wiring: `run_started`, step seeding/completion, resume from the journal's
  completed prefix, commit recorded as an effect keyed by `(run, delta)`, and
  `run.json.journal` as the fold.
- No dispatcher, no concurrent workers, no Postgres: those are the ADR's
  triggers (023 needs more than one worker).

## Non-goals

- Replacing `progress.json`/`events.jsonl` as operator views.
- Leases across machines, a step queue dispatcher, or a worker pool.
- Changing QA-only evidence, scope guards or the commit trailers.
- A UI for the journal.

## Acceptance criteria

- **AC-1 — Idempotent events.** `append(run, type, key=...)` writes once per
  `(run, key)`; a repeated key is a no-op. Events carry time, type, step,
  attempt and payload and are read in order.
- **AC-2 — Step leases.** Steps are seeded; `claim_step` takes a live lease and
  refuses a second owner; a lease older than its TTL is claimable; `done` is not
  claimable; `heartbeat` extends only the owner's lease.
- **AC-3 — Step completion and resume.** `complete_step` records the status,
  digest and the bounded output; `completed_outputs` returns the contiguous done
  prefix, and the flow uses it when it is longer than `progress.json` (recovery
  note `journal`).
- **AC-4 — Effect keys.** `record_effect`/`effect` make commit idempotent: the
  flow checks `commit:<run>:<delta>` before `_commit_changes` and records the
  result after. A repeated run of the same delta cannot create a second commit.
- **AC-5 — Projection.** `fold(run)` returns status, events count, steps and
  effects; `run.json.journal` carries it, so the record is auditable.
- **AC-6 — Tests and docs.** `make swarm-test` covers events, leases/expiry,
  completion/resume, effects and the fold; `025-durable-journal` is in
  `HARNESS_SPECS`; AGENTS/roadmap/changelog record the slice and its limits.

## Evidence

ADR-012 option C, `specs/013` (progress checkpoints, approval resume),
`specs/015` (evidence, effects), the 020–024 runs (crash/duplicate risk).

## Success definition

A killed run resumes from the journal's completed steps, and a retried commit
is a no-op, with `run.json` unchanged as the view and green still QA-owned.
