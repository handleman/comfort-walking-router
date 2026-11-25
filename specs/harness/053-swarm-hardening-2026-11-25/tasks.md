# 053 Swarm Hardening (2026-11-25) — Tasks

Each task maps to one acceptance criterion.

- [ ] T1 (AC-1): Grounded reviewer block — `blocked` with all recorded gates green + verifier passed + no concrete cited evidence → `reviewer_blocked_ungrounded` and stop (no fix round); a cited failing gate/AC/file:line still proceeds.
- [ ] T2 (AC-2): Delta guard reference rule — a backtick path under a `use/from/via/see/read` clause is a reference, not a required change; only ownership verbs require it. Regression fixture: the T6 brief naming an already-implemented `helpers.ts` still goes green.
- [ ] T3 (AC-3): Per-task write allowlist — derive from the brief's ownership paths + plan step targets; revert other delta writes (`out_of_scope_reverted`); `e2e_required` keys off the allowlist.
- [ ] T4 (AC-4): e2e launch classification — a spawn/launch error is `{"ran": false, "error": ...}` → class `env`; "ran, no parseable failures" stays `unclassified` and says so.
- [ ] T5 (AC-5): `inner.MAX_TASKS` raised (or roster batched) so an 11-failure migration gets a repair round; `swarm/health.py` + `make swarm-health` runs `pytest -q` and the e2e suite, exit non-zero on failure.
- [ ] T6 (AC-6): one test per AC; `pytest swarm/tests/`, `ruff`, `mypy` green.
