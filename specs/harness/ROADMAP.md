# Harness implementation order

> **Historical record (2026-11-26).** The harness now lives in the published
> [handleman-hq](https://github.com/handleman/handleman-hq) repo and this app
> consumes it as a package. This page records the order the factory was built
> in; new harness work belongs upstream. The live order is
> [handleman-hq/specs/harness/ROADMAP.md](https://github.com/handleman/handleman-hq/blob/main/specs/harness/ROADMAP.md).

**Revised 2026-11-26** after the overnight run. Follow top to bottom; update the
status box as work lands.

Status: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` dropped.

## Done

- `[x]` **051** acceptance artifacts commit — `0855cbc`.
- `[x]` **Bookkeeping** — `2e6aeb3` (ticked 042 T1/T2, 043 T1–T6/T8, 044, 045).
- `[x]` **052** layout geometry + control presence — `3d63342` (live
  `layout_failures: NONE`).
- `[x]` **040 T23** the map never initialised (`onDestroy` inside `onMount`) —
  swarm-authored `c7b559c`.
- `[x]` cost bug: `usage._rate` missed the `opencode-go/` prefix, so the dollar
  cap could not fire — fixed (`3ccb09c`).
- `[x]` reviewer model `mimo-v2.6-flash` → `qwen3.8-flash` (it blocked without
  evidence). Lesson: judgement roles need reasoning, not the cheapest tier.
- `[x]` host sleep is no longer a fake model timeout — `swarm/power.py`
  (`caffeinate -ims -w <pid>`, `SWARM_KEEP_AWAKE=0` off) and
  `events.suspension_gap()` → `run.json.host_suspended` + reason code
  (`c0b77f1`, `d0b4b30`).

## Phase A — make the harness trustworthy

1. `[x]` **053 swarm hardening** — grounded blocks, reference-vs-required paths,
   per-task allowlist, e2e launch = `env`, roster cap 12 + `make swarm-health`
   (`dde8ee6`, 20 tests).
2. `[x]` **040 T6 e2e migration + T24** — the five specs run the 040 auto-plan
   flow; `npm --prefix frontend run test:e2e` → **9 passed / 3 skipped**. T24 was
   an oracle defect, not an app defect (see the acceptance row below).
3. `[x]` **`make swarm-health`** — real run catches a red suite and now prints
   the Playwright summary instead of uvicorn noise (`f9ded20`).

## Phase B — close cheap leftovers

4. `[x]` **047 leftovers** — `Profile.crew_timeout()` (cloud 300 / local 900),
   `flow._role_provider` reads the Profile, fallback ids validated against the
   provider catalogue, docs collapsed to `swarm/docs/setup.md` (`bcaec1a`,
   merged `ab4fc2b`).
5. `[x]` **050 leftovers** — four-state `geolocation.spec.ts` (allowed / position
   moves / denied / unavailable, `738aaa0`); T1/T2 dropped with the
   recorded-corridor fixture rationale.

## Phase C — productization (the original goal, last)

6. `[~]` **048 Phase 2–3** — packaging and the factory test split are done in
   `/tmp/hq-src3` (fresh 240-commit filtered history): **833 passed, 8 skipped**,
   `-m "not driver"` green with no app tree, ruff clean, `__pycache__` purge and a
   factory `.gitignore`/`.dockerignore`/Makefile. **T8/T9/T9b/T10/T12 done**; **v0.3.0 released** (target-agnostic core, drivers
  isolated under `swarm.drivers`); T9 consumers wired (scope/gate_map/gates/risk/
harness_specs read the contract, env wins). **T9b discovered:** 30 tests encode the app's scope, so generic defaults wait for the app's `swarm.yaml` (Phase 5). Then T10's core-agnostic grep, T11–T12 drivers.
   *Earlier note:* packaging is done locally in `/tmp/hq-src2`
   (233-commit filtered history): `src/swarm/`, `swarm/paths.py` as the one
   `REPO_ROOT`, `handleman-hq` pyproject (hatchling, `hq = swarm.cli:main`),
   `hq --version` / `hq init` verified; secret scan of the filtered history is
   **clean** (`ff0e750`). **Blocking discovery:** the factory suite is app-coupled
   — 835 pass with the app present, 21 fail without it (app fixtures, source
   paths, driver imports). `T5b` in `048/tasks.md` splits core tests from driver
   tests; `swarm.yaml` contract + driver relocation follow (`T8`–`T12`).
7. `[~]` **048 Phase 7** — **published**: https://github.com/handleman/handleman-hq
   (public, MIT, filtered 240-commit history, secret-scanned), released
   **v0.2.1** (packaged `hq` 0.2.1 + installed-root fix; v0.2.0 superseded).
   Verified by installing from the tag in a clean venv (`hq --version` → 0.2.1).
   **Remaining:** the app pins `git+…@v0.2.1` and drops its vendored `swarm/`
   (T19/T20) — that migration needs T11's driver split first, because `smoke`,
   `corridor_check` and `db.sh` are app-side drivers the package does not ship.
8. `[ ]` **038** — any ejectable-contract bits not folded into 048.

## Acceptance stand (043) — corrected 2026-11-26

`make swarm-accept` → **PASS**; 040 checks 8/8. Four false negatives fixed
(`44989c9`): the preview proxy ignored the port the stand started (`AC-8` could
never fire); `AC-7` counted empty `.error` placeholders and browser 503s from the
DB-less saved-routes feature; `AC-6` looked for aria-labels on decorative icons;
the zero-size check counted controls hidden by an ancestor. The criteria parser
now also reads the older `- [x] AC-n:` headers, so ten specs stop reporting 0/0/0
(they remain **unverified** until each gets an `acceptance.toml`).

- `[x]` **054 T6 test-first UI** — the fix and senior prompts carry QA's suite
  tail (failing spec + error), and the self-heal's repair crew gets the digest;
  success is the recorded suite passing at the delta.
- `[x]` **054 T8 no-regression** — 855 swarm / 197 app tests, ruff + mypy green.

**054 is complete.**
- `[x]` **054 T3 oracle self-test** — `swarm-accept --selftest` mutates each
  check's target and requires the check to fail (040: every mutatable check OK;
  absent/count=0 reported UNSUPPORTED, not silently green); uncovered ACs are a
  configuration warning, fatal with `--strict`.
- `[x]` **054 T7 core/driver split** — the factory suite marks app-coupled tests
  `driver` and skips without an app tree: `pytest -m "not driver"` is green with
  no `app/` (833 passed, 8 skipped in `/tmp/hq-src3`).
- `[x]` **054 T2 evidence-backed PASS** — a PASS with a required e2e execution
  missing is `review_unsupported` (judge record names the command); a harness
  run that passes clears the flag.
- `[x]` **054 T4 reconcile fix tasks** — the acceptance pass ticks an open
  `(acceptance pass …)` task whose every referenced AC now passes (ranges and
  multi-AC tasks wait); T19–T21 can never be re-queued after going green.
- `[x]` **054 T5 factory audit** — `python -m swarm.factory_audit` /
  `make factory-audit` rejects tracked caches, secret-shaped files, blobs over
  1 MB and missing hygiene; the filtered factory passes its own gate.
- `[x]` **054 T1 fresh build** — `frontend/e2e/global-setup.ts` builds before any
  suite run (`npx playwright test`, the npm script, `swarm.e2e`); the stale
  `dist/` signal is gone (`da142e0`-era doc, code this change).

## Open follow-ups

- `[ ]` **042 T3/T4** visual phase integration — `_visual_phase` is a stub.
- `[x]` **043 T7** acceptance re-queue — one re-entry when the pass queued or
  reconciled fix tasks; a second failing round stops honestly.
- `[x]` **049 T8** real-run verify — the senior escalation ran on T6's verifier
  block (2026-11-26, `senior:verify1`) and the run recovered.
- `[ ]` **040 T25 modal recovery** — choosing a suggestion inside `StartLocationModal` does not close it and the click never reaches the option's handler (T25 run 2026-11-26 parked `e2e_rounds_exhausted`; the coder's SearchInput edit was correctly blocked by the reviewer and reverted).
- `[~]` **Acceptance coverage** — 040 (8/8), **028** and **039** now have
  `acceptance.toml` checks and pass; every uncovered AC is a loud configuration
  warning. Remaining specs: 001, 004, 005, 006, 007, 008, 010, 011, 014, 029, 035,
  036 (many are API/infra ACs with no browser surface).
- `[x]` **`done.json` cache key** — `record_done` normalises through
  `spec_dir_name`, so the cache and the trailers agree.
- `[ ]` **QA can skip the e2e command** — the harness now runs the suite itself
  when nothing was recorded (`1711c5b`), but QA reporting PASS without running it
  is still accepted until the evidence check fires; consider failing the verdict.

## Known issues

- Host sleep (not provider latency) was the real cause of the 55-minute stall;
  `caffeinate` now holds the machine, and a silent gap is recorded as
  `host_suspended`.
- `tasks.md` checkboxes are intentionally stale; the commit-trailer ledger is the
  source of truth (`make swarm-report`, not the checkboxes).

## Dependencies

```
053 ─→ 040 T6 + T24 ─→ swarm-health          (all done)
047 ──────────────────────────────────────→ 048 Phase 2-3 ─→ 048 Phase 7
050 (independent)                            (done)
048 T5b (test split) ─→ T7 (factory green) ─→ T8–T12 ─→ Phase 7
```
