# Harness implementation order

**Agreed 2026-11-23. Follow top to bottom.** Update the status box as work lands;
do not reorder without a reason written next to the item.

Status: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` dropped.

## Order

1. `[~]` **051 — acceptance artifacts commit.** The acceptance pass commits its
   own `acceptance.md` + queued `tasks.md` fix tasks (direct commit on the
   branch; skip on held runs; `SWARM_ACCEPT_COMMIT=0` off). *Small; in flight;
   removes a recurring manual step.*
2. `[ ]` **Bookkeeping.** Tick the tasks whose code is already in: **042**
   (visual QA), **043** (acceptance pass), **044** (skills), **045** (agent
   dedup), and **049 T8** (real-run verify). Keeps "what's left" honest.
3. `[ ]` **052 — layout geometry + control presence** (+ product **040 T22**
   data-testids). Deterministic DOM checks (`present`, `unique`, `in_region`,
   `region_visible/hidden`, `region_order`, `no_overlap` peers-only,
   `no_overflow`) from `layout.toml`; no pixels, no vision; gates + queues fixes;
   Figma seam via the `data-testid` IR. *Makes layout verification harness-owned.*
4. `[ ]` **T6 re-scope.** With 052 in place, "verify the layout" is a harness run,
   so 040 T6 stops being an unfixable coder task (or retry it with a longer crew
   cap). *Closes the `e2e_unclassified` parking.*
5. `[ ]` **050 — corridor reliability stand.** vcrpy cassettes for the real
   Overpass parse path, mocked failover/timeout tests, `make corridor-check` live
   probe, and the Playwright geolocation contract (allowed/denied/unavailable/
   moved). *Independent of 052; can run in parallel.*
6. `[ ]` **047 — model-config consolidation.** One `swarm/model_config.py`
   (ROLES, router, free predicate, typed `Profile`); env names unchanged. *Do it
   in a quiet window — no live run. Consolidate before extracting a repo.*
7. `[ ]` **038 → 048 — productization.** 038 (ejectable `swarm.yaml` + `hq` CLI +
   `swarm init`) then 048 (multi-repo split: comfort-walking-router +
   handleman-hq, history split, public repo, driver relocation). *Last: highest
   risk, and it inherits everything above.*

## Dependencies

```
051 ─→ (bookkeeping) ─→ 052 ─→ T6 re-scope
050 ──────────────────────────────┘   (parallel)
047 ──────────────────────────────────→ 038 ─→ 048
```

- 052 needs 040 **T22** (the swarm adds `data-testid`; the harness only consumes).
- 048 realizes 038; do 047 first so the extracted factory has one model-config
  source, not two.
- 050 and 052 touch different surfaces (app drivers vs harness acceptance) — safe
  to run in the same period.

## Definition of done (each item)

- code + tests, `pytest swarm/tests/ -q`, `ruff check swarm/`, `mypy app tests`
  green; the spec's tasks ticked; committed with the spec slug in the message.
- Product tasks (T22, T6) go through the **queue** (`specs/product/`), not direct
  edits.

## Why this order (one line each)

- **Verification first:** a factory that cannot trust its own green does not
  deserve its own repo (051 → 052 → T6).
- **Bookkeeping second:** cheap, and it makes the remaining list actionable.
- **App reliability next:** 050 is orthogonal and strengthens 039.
- **Cleanup before the split:** 047 removes duplicated config knowledge *before*
  it gets copied into a second repo.
- **Productization last:** 038/048 are the irreversible-ish steps (public repo,
  history rewrite).
