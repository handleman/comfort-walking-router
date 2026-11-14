# 023 Parallel Factory — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [x] T1 (AC-1): worker isolation — detached worktree at HEAD, current harness copy, repo venvs, `swarm.flow --no-commit`, scope-filtered changed files and a binary diff; the main tree is never written.
  Evidence: `swarm/parallel.py::run_worker`, `swarm/tests/test_parallel.py`.
- [x] T2 (AC-2): independence grouping by the files each brief names; a group is mutually independent and phase 1 takes up to `SWARM_WORKERS` from one group.
  Evidence: `swarm/parallel.py::independent`, `swarm/tests/test_parallel.py`.
- [x] T3 (AC-3): serialized integration — `git apply --check`, apply, full `SWARM_GATE_COMMANDS` on the main tree, commit with `Swarm-Task`/`Task-Hash`/`Spec-Hash`/`Swarm-Parallel` trailers, best-effort push.
  Evidence: `swarm/parallel.py::integrate`, `swarm/tests/test_parallel.py`.
- [x] T4 (AC-4): conflict/gate/commit rollback — `git apply -R` on failure, explicit statuses, the task stays open and the main tree clean.
  Evidence: `swarm/parallel.py::integrate`, `swarm/tests/test_parallel.py`.
- [x] T5 (AC-5): `run_batch` — one thread per chosen task, results queue, integration serialised on the caller; per-task outcomes and `integrated` count.
  Evidence: `swarm/parallel.py::run_batch`, `swarm/tests/test_parallel.py`.
- [x] T6 (AC-5, AC-6): `make swarm-parallel` CLI, `SWARM_WORKERS`, docs and the honest measurement note (live throughput not measured until a green baseline exists).
  Evidence: `swarm/parallel.py::main`, `Makefile`, `swarm/README.md`, `docs/research/fix-loop-2026.md`.

## Decisions (2026-11-14)

- **Race, not scheduler.** Independent tasks are attempted concurrently; the
  first green is integrated and the rest stay open. A durable queue/leases are
  ADR-012's future option, not this phase.
- **The main tree has one writer.** Workers are `--no-commit`; integration is
  serial and re-gates, so the merge evidence is a serial run's evidence.
- **Phase 1 stays at one group.** Files shared between briefs are the main
  correctness risk; taking workers from one independent group removes it without
  a dependency graph.
- **Measurement is honest.** The code is tested without an LLM; live throughput
  is not claimed until a green baseline exists (021/022 have none yet).

## Phase 023 evidence

021/022 measured 10–16 minutes for a two-file task and no green live replay yet.
The parallel module is therefore shipped as tested orchestration, with the live
throughput comparison recorded as pending.
