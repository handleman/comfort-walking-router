# 025 Durable Journal — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [x] T1 (AC-1): `swarm/journal.py` — append-only events with an idempotent `(run, key)`, nullable key for notes, ordered reads.
  Evidence: `swarm/journal.py`, `swarm/tests/test_journal.py`.
- [x] T2 (AC-2): step leases — seed, atomic claim (not done, free/expired), owner-only heartbeat, expiry.
  Evidence: `swarm/journal.py`, `swarm/tests/test_journal.py`.
- [x] T3 (AC-3): step completion/resume — status + digest + bounded output, contiguous completed prefix, flow merges it with the checkpoint.
  Evidence: `swarm/journal.py`, `swarm/flow.py`, `swarm/tests/test_journal.py`.
- [x] T4 (AC-4): commit as an idempotent effect keyed by `(run, delta)`; `_commit_green` checks before and records after.
  Evidence: `swarm/flow.py`, `swarm/tests/test_journal.py`.
- [x] T5 (AC-5): `fold(run)` and `run.json.journal`; `run_started`/`run_status` events.
  Evidence: `swarm/journal.py`, `swarm/flow.py`, `swarm/tests/test_journal.py`.
- [x] T6 (AC-6): `025-durable-journal` in `HARNESS_SPECS`, AGENTS/roadmap/changelog, tests green.
  Evidence: `swarm/flow.py::HARNESS_SPECS`, `AGENTS.md`, `docs/roadmap.md`.

## Decisions (2026-11-14)

- **Option C, first slice.** In-repo SQLite journal, crews as activities, one
  writer. Postgres/dispatcher/workers wait for the ADR triggers (023 >1 worker).
- **The journal does not own green.** Steps/effects are durable; QA's recorded
  evidence still decides green.
- **Effects are keyed by content.** `commit:<run>:<delta>` makes a retry a no-op
  without hiding a genuinely different delta.
- **Keep the views.** `events.jsonl`, `progress.json` and `run.json` remain; the
  journal is the authority behind them, not a second UI.
