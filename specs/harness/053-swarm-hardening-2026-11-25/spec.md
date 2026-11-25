# 053 Swarm Hardening (2026-11-25) — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The 2026-11-25 T23/T6 session cost hours to five harness failure modes, none of
which was the code under test. Each is reproducible from the run records:

1. **A reviewer blocked without evidence.** T23 ended `review_verdict=blocked`
   with cause `test` while every recorded gate was green
   (`npm check/lint/test` = 0), the verifier passed, and **no `pytest` run
   existed** in `shell_log.jsonl`. The fix round chased that non-existent
   failure, changed nothing (`changed: false`), and the run died `no_progress`.
   `block_is_grounded` matched nothing concrete and still allowed a fix round.
2. **A referenced path was treated as required work.** T6's brief said "use
   `planRoute(...)` from `frontend/e2e/helpers.ts`". The coder correctly migrated
   all five specs, but the delta guard read the backtick path as *required*, saw
   `helpers.ts` `untouched`, and stopped `delta_incomplete`, reverting the specs.
3. **Off-scope edits had cross-cutting effects.** T23's coder touched
   `frontend/e2e/helpers.ts` and `app/saved_routes.py`; the helper edit flipped
   `e2e_required` on a *map* task, which then could never record a green suite.
4. **A launch failure hid as "unclassified".** `playwright.config.ts` had
   `webServer.cwd: 'frontend'` (resolves to `frontend/frontend` → `spawn /bin/sh
   ENOENT`). The e2e self-heal saw no parseable failures and stopped
   `e2e_unclassified` for three runs, hiding the cause.
5. **A cap silently refused big repairs.** `SWARM_MAX_INNER_TASKS` defaults to 3;
   >3 failures ⇒ `e2e_roster_overflow`, no repair. An 11-failure stale suite was
   unwinnable. Separately, the suite could not launch and nothing noticed until
   an explicit `make e2e`.

**Already applied (config, not code):** the reviewer model was
`mimo-v2.6-flash` and blocked spuriously; switching it to `qwen3.8-flash` (the
verifier's model) let the same work pass. Judgement roles need reasoning, not the
cheapest tier — see 047's profile table.

## Goal

Make each failure mode impossible or loud:

1. **Grounded block.** A `blocked` verdict that cites no recorded failing gate,
   AC, file:line or test (when all recorded gates are green and the verifier
   passed) is `reviewer_blocked_ungrounded`: the run stops without a fix round.
2. **Reference ≠ required.** A brief that *references* a file it does not need to
   change must not create a required delta. Extend the 030 read-verb rule to
   `use`/`from`/`see`/`via`.
3. **Per-task write allowlist.** The flow derives the task's writable set from
   the brief's named files (+ the plan's files) and reverts writes outside it,
   not only writes outside the global scope. `e2e_required` keys off the task's
   target files, not any touched path.
4. **Launch failure is `env`.** A spawn/launch error in a suite run is class
   `env` with the error text; "no failures parsed" distinguishes "the suite never
   ran" from "it ran and produced no parseable failures".
5. **No silent cap / silent stand.** Raise (or batch) the e2e roster cap; add
   `make swarm-health` (or a preflight smoke) that runs the app + e2e suites so a
   broken test stand fails fast instead of on the one task that owns e2e.

## Acceptance criteria

- [ ] **AC-1 (grounded block):** a reviewer `blocked` with all recorded gates
  green and the verifier passed, and no concrete evidence, ends
  `reviewer_blocked_ungrounded`; no fix round runs. A block that cites a real
  failing gate/AC/file:line still proceeds to the fix loop.
- [ ] **AC-2 (reference vs required):** a brief that mentions a file with
  "use/from/via/see X" does not add it to the required delta; a task whose only
  referenced files already satisfy it can go green without touching them.
- [ ] **AC-3 (per-task scope):** a write outside the task's allowlist is reverted
  and recorded (`out_of_scope_reverted`), even when the path is inside the global
  scope; a write to `frontend/e2e/*` on a non-e2e task does not set
  `e2e_required`.
- [ ] **AC-4 (launch errors):** a suite that fails to launch records class `env`
  with the error text; the record distinguishes "suite did not run" from "no
  parseable failures".
- [ ] **AC-5 (caps + health):** `SWARM_MAX_INNER_TASKS` default is high enough
  (or the roster is batched) that an 11-failure migration gets a repair round;
  `make swarm-health` runs the app + e2e suites and exits non-zero on a broken
  test stand.
- [ ] **AC-6 (no regression):** `pytest swarm/tests/`, `ruff`, `mypy` green; the
  existing verifier/QA/self-heal tests still pass.

## Files

- `swarm/flow.py` — grounded-block gate, delta reference rule, per-task allowlist,
  e2e launch classification.
- `swarm/evidence.py` / `swarm/guards.py` — recorded-gate lookup for the block.
- `swarm/e2e_triage.py` / `swarm/e2e.py` — launch-error shape.
- `swarm/inner.py` — roster batching or a higher default.
- `swarm/health.py` + `Makefile` — `make swarm-health`.
- `swarm/tests/` — one test per AC.
