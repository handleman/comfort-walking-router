# Harness implementation order

**Agreed 2026-11-23. Follow top to bottom.** Update the status box as work lands;
do not reorder without a reason written next to the item.

Status: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` dropped.

## Order

1. `[x]` **051 — acceptance artifacts commit.** *Done 2026-11-23 (`0855cbc`).*
   The pass commits its own `acceptance.md` + queued `tasks.md` fix tasks
   (direct commit; skip on held runs; `SWARM_ACCEPT_COMMIT=0` off).
2. `[x]` **Bookkeeping.** *Done 2026-11-23.* Ticked 042 T1/T2, 043 T1–T6/T8,
   044 T1–T5, 045 T1/T2/T3/T5/T6. It also found real gaps — see below.
3. `[x]` **052 — layout geometry + control presence** (+ product **040 T22**).
   *Done (`3d63342`): `swarm/layout.py` IR + pure evaluator, acceptance wiring,
   `.mjs` fact collector, 040 `layout.toml`, 11 tests; a live pass on 040 reports
   `layout_failures: NONE` at desktop + mobile. Two refinements remain (route-
   planned state, mobile-drawer-open state) — see the spec's T4.*
4. `[x]` **T6 re-scope.** *Done 2026-11-24: retired as a coder task — QA runs
   `npm check`/`npm test` on every task and the 043+052 acceptance pass verifies
   the hooks in a real browser (`layout_failures: NONE`). 040 is now fully
   closed (`open: []`, `resume_point: None`).*
5. `[ ]` **050 — corridor reliability stand.** vcrpy cassettes, mocked
   failover/timeout tests, `make corridor-check`, Playwright geolocation contract.
   *Independent of 052; can run in parallel.*
6. `[ ]` **047 — model-config consolidation.** One `swarm/model_config.py`;
   env names unchanged. *Quiet window — no live run.*
7. `[ ]` **038 → 048 — productization.** 038 (`swarm.yaml` + `hq` CLI + `init`)
   then 048 (multi-repo split). *Last: highest risk.*

## Discovered during bookkeeping (2026-11-23) — inserted into the verification track

- `[ ]` **042 T3/T4 — visual phase integration.** `_visual_phase` is a stub that
  returns `True`; `build_visual_qa_crew`/`visual.py` exist but are never invoked,
  there is no `SWARM_VISUAL_QA` switch and no `visual_blocked` stop. Real work,
  and it belongs with 052 (verification quality).
- `[ ]` **043 T7 — acceptance re-queue.** The supervisor runs the acceptance pass
  at drain but does not re-enter the queue when fix tasks were queued; a FAIL
  stops instead of running the fixes. Small, pairs with the 052/T6 verification
  work.
- `[ ]` **049 T8 — real-run verify.** Needs one live run on a previously-parked
  task (piggyback on the next queue run).

## Known issues (2026-11-24)

- **`make e2e` cannot launch in the sandboxed agent shell**: `Failed to launch:
  Error: spawn /bin/sh ENOENT` (the fixture backend starts; the Playwright
  browser/webServer spawn fails). The swarm's own e2e runs have succeeded, so
  this is an agent-shell environment limit, not a suite regression. Track e2e
  results from a normal terminal.

## Dependencies

```
051 → bookkeeping → 052 → T6 re-scope
                       ├─ 042 T3/T4
                       └─ 043 T7
050 ─────────────────────┘   (parallel)
047 ─────────────────────────→ 038 → 048
```

- 052 needs 040 **T22** (the swarm adds `data-testid`; the harness consumes).
- 048 realizes 038; do 047 first so the extracted factory has one model-config
  source.
- 050 and 052 touch different surfaces — safe to run in the same period.

## Definition of done (each item)

- code + tests, `pytest swarm/tests/ -q`, `ruff check swarm/`, `mypy app tests`
  green; the spec's tasks ticked; committed with the spec slug in the message.
- Product tasks (T22, T6) go through the **queue** (`specs/product/`), not direct
  edits.

## Why this order (one line each)

- **Verification first:** a factory that cannot trust its own green does not
  deserve its own repo (051 → 052 → T6, plus the 042/043 gaps found above).
- **Bookkeeping second:** cheap, and it makes the remaining list actionable.
- **App reliability next:** 050 is orthogonal and strengthens 039.
- **Cleanup before the split:** 047 removes duplicated config knowledge *before*
  it is copied into a second repo.
- **Productization last:** 038/048 are the irreversible-ish steps.
