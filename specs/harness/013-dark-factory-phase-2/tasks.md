# 013 Dark-Factory Phase 2 — Tasks

Control-plane spec: `013-dark-factory-phase-2` is added to `HARNESS_SPECS`, so the queue never implements it. Run these explicitly or by hand, and mark `[x]` only after green + review.

- [x] T1 (AC-1, AC-3): Add `swarm/done.py` with `task_hash(task)` (id+brief+ACs) and `done_entries(repo_root)` parsing `Swarm-Task`/`Swarm-Task-Hash` commit trailers from a bounded git log; add `swarm/tests/test_done.py` using a temp git repo.
- [x] T2 (AC-1, AC-4): Emit `Swarm-Task`, `Swarm-Task-Hash`, and `Swarm-Run` trailers from `_commit_changes` in `swarm/flow.py` (new `task_hash`/`run_id` args, same message for direct and merge modes); extend `swarm/tests/test_autoloop.py`.
- [x] T3 (AC-1, AC-2): Filter green-but-unchecked tasks out of auto-advance and `_resume_point` in `swarm/flow.py` using `swarm/done.py`, while keeping an explicit `SPEC TASK` run override; add resume/queue tests.
- [x] T4 (AC-5, AC-6): Record `delta_hashes` + git `head` on `awaiting_approval`, and add `approve_held_run(spec, task)` in `swarm/flow.py` that verifies HEAD/hashes, commits the held delta via `_commit_changes`, and rewrites that `run.json` to `green`; add mismatch/refusal tests.
- [x] T5 (AC-5): Wire the held-run path into `--approve` (`swarm/flow.py`), `make swarm-approve` (`Makefile`), and TUI `a` (`swarm/tui.py`) with ledger fallback when no held run exists; add tests.
- [x] T6 (AC-7): Write an atomic `progress.json` in the run dir after every completed micro-step in `swarm/flow.py` (plan hash, steps, completed index, step output tails, delta hashes); add `swarm/tests/test_progress.py`.
- [x] T7 (AC-8, AC-9): Resume an interrupted/killed task from `progress.json` in `swarm/flow.py` when plan+hash match (skip completed steps, reuse outputs, record `resumed_from_step`/`recovery`), otherwise restart with a reason; add fake-crew resume tests.
- [x] T8 (AC-10): Surface done-ledger hits, approval result, and checkpoint resume in `run.json`/the dashboard, and update `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`, `changelog.md`; run `make test`, `make swarm-test`, `make lint`, `make typecheck`, frontend `npm run check`/`build`.

Phase 2 evidence (2026-11-08): done ledger from git trailers + cache fallback (spec/plan hashes reopen stale tasks); held-run approval commits the verified delta via the merge queue; atomic per-step `progress.json` resumes killed runs with plan/file/age validation; 174 harness tests, app tests, ruff/mypy clean.
