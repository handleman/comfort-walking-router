# 054 Signal Integrity — Plan

References `specs/harness/054-signal-integrity/spec.md` AC-1–AC-7.

## Approach

Smallest change that removes each false signal, in cost order. AC-1 first: a
stale build invalidates every other e2e conclusion and cost ~40 minutes of
misdiagnosis. AC-3/AC-4 next: the acceptance stand judged the product with broken
oracles and left stale fix tasks. AC-5 protects the one irreversible surface.
AC-6/AC-7 unblock the factory.

## Steps

1. **Fresh build (AC-1).** Add `pretest:e2e` (`npm --prefix frontend run build`)
   or fold the build into the preview `webServer` command; keep one path so a
   raw `npx playwright test` is also fresh. Record `built_at` in the e2e
   execution tail. Test: edit a visible string, run the suite with no explicit
   build, assert the change is seen.
2. **Evidence-backed PASS (AC-2).** After parsing the review verdict, if it is
   `pass` and `e2e_required` and no e2e execution exists at the current delta,
   re-ask once with the missing command; if still missing, set
   `review_unsupported` and stop (the harness-run suite stays as the fallback).
3. **Oracle self-test (AC-3).** `acceptance.py --selftest`: for every declared
   check, (a) assert the selector matches (or the route_request fires) on the
   current build, and (b) run a mutated-DOM variant where the target is removed
   and assert the check fails. Report a check that can pass on an empty page as
   `oracle_always_passes`. Treat criteria-without-checks as a configuration
   problem in the summary.
4. **Reconcile fix tasks (AC-4).** When a task's brief says `(acceptance pass …)`
   or the task carries `acceptance`, evaluate the named AC against the latest
   acceptance verdict; if it passes, record the task done (ledger trailer) and
   skip the run, with `skip_reason=acceptance_reconciled`.
5. **Factory audit (AC-5).** `scripts/factory_audit.py`: tracked `__pycache__`,
   `*.pyc`, `node_modules`, `.env*` (except `.env.example`), blobs > 1 MB,
   missing `.gitignore`/`.dockerignore`/`LICENSE`; wire as `make factory-audit`
   and run it in 048 Phase 7 before the push.
6. **Test-first UI (AC-6).** When the recorded failure names a spec, the fix
   crew's prompt includes the spec path + failure tail and its expected output is
   "that spec passes"; the gate is `npx playwright test <spec>` at the delta.
7. **Core/driver split (AC-7).** `pytest.ini` markers `driver`; app-coupled tests
   get `pytest.mark.driver` + a skip when `app/` is absent; `make test-core`
   runs `-m "not driver"`.

## Risks

| Risk | Mitigation |
| --- | --- |
| Build on every suite run is slow | build only when `dist/` is older than `src/` (mtime check) |
| Selftest needs a known-good page | run against the fixture backend; skip with a reason if unavailable |
| Reconciling fix tasks hides a real regression | only close when the AC passes in a *fresh* acceptance run (same session) |
| Driver markers hide coverage in the app repo | the app keeps running the full suite; only the factory skips |

## Rollback

Each step is an env-guarded switch (`SWARM_E2E_BUILD=0`, `SWARM_ACCEPT_SELFTEST=0`,
`SWARM_ACCEPT_RECONCILE=0`, `SWARM_FACTORY_AUDIT=0`).
