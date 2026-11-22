# 047 Model Config Consolidation — Plan

References `specs/harness/047-model-config-consolidation/spec.md` AC-1–AC-8.

## Approach

Move knowledge, not behaviour. The refactor is a sequence of **behaviour-
preserving** moves, each with a golden test that pins the resolved profile
before and after, so a regression is a test failure rather than a bad night run.

Order matters: build the resolver first, migrate consumers one at a time, then
delete the old copies. At no point are two sources of truth authoritative.

## Step 0 — Pin the current behaviour (before any move)

`swarm/tests/test_model_config.py::test_checkout_profile_is_unchanged` records
the checkout's resolved profile (role → model, provider, fallback, crew cap) as a
literal expectation. It is written against today's code path (`llms`), passes
immediately, and must keep passing after every step.

## Step 1 — `swarm/model_config.py` (new module)

- `Role` dataclass: `name`, `model_var`, `fallback_var`, `vision: bool`,
  `optional: bool` (the verifier inherits the senior model).
- `ROLES`: planner, coder, reviewer, senior, verifier (optional), visual,
  accept, conflict (reuses the coder model).
- `provider(model)`: the one prefix router (`ollama/`, `zen/`, `opencode-go/`,
  else `openrouter`).
- `is_free(model)`: the one free predicate (`ollama/`, `:free`, `-free`,
  `contributor-free`).
- `Profile`: resolved per run from a mapping (default `os.environ`), with
  `role()`, `paid_allowed`, `crew_timeout()`, `llm_timeout(model)`,
  `problems()`.
- CLI: `python -m swarm.model_config show` (AC-5) prints the table the
  dashboard/preflight use.

Timeouts move here as the *only* defaults: crew 300/900 (cloud/local),
per-generation `SWARM_LLM_FIX_TIMEOUT_SECONDS` vs `SWARM_OLLAMA_TIMEOUT_SECONDS`
(defaults unchanged). Env overrides still win, exactly as today.

## Step 2 — Migrate `llms.py`

- `_guard` / `_paid_ok` call `model_config.is_free` and `Profile.paid_allowed`
  (single switch, 684e269).
- Builders (`planner_llm`, `coder_llm`, …) take the resolved `Model` from
  `Profile.role(...)`; the `allow_paid` kwarg stays accepted and inert.
- `_fix_timeout` / Ollama timeout become `Profile.llm_timeout(model)`.
- `ROLE_MODEL_VARS`, `uses_local_models`, `crew_timeout_seconds` become thin
  re-exports (kept one release for compatibility; marked deprecated).

## Step 3 — Migrate `preflight.py`

- Delete `ROLE_VARS` / `OPTIONAL_ROLE_VARS`; iterate `Profile.roles`.
- Delete the per-provider ping branches; ask `Profile.problems()`, which pings
  each provider **once** and validates role ids **and** fallback ids (AC-6).
- Keep the venv/gate/e2e checks where they are (not model config).

## Step 4 — Migrate `flow.py`

- `_fallback_key(role)` → `model_config.ROLES` lookup.
- `_role_provider(role)` → `Profile.role(...).provider` (fallback-aware).
- `_kickoff`'s crew cap → `Profile.crew_timeout()`.

## Step 5 — Migrate `usage.py`

- `is_free` imported from `model_config` (delete the local copy); price table
  stays (it is data, not policy).

## Step 6 — Docs

- `swarm/docs/setup.md` becomes the single canonical description of profiles,
  routing, guard and timeouts.
- `AGENTS.md` / `GLOSSARY.md` / `docs/reference.md` keep one-line statements and
  link to it (AC-8).

## Step 7 — Verify

- `pytest swarm/tests/ -q` (774+), `ruff check swarm/`.
- `python -m swarm.model_config show` matches the golden profile from Step 0.
- `SWARM_ALLOW_PAID=0` refuses a Go id; `=1` allows it.
- A local override (`SWARM_CODER_MODEL=ollama/...`) yields the 900 s cap.
- `python -m swarm.preflight` offline and live both report 0 problems.
- One real task (`make swarm-run SPEC=040 TASK=T13`) still goes green.

## Risks

| Risk | Mitigation |
|---|---|
| A consumer silently keeps the old copy | Step 0's golden test + AC-1..AC-4 tests assert the derivation, not just the value |
| Timeout drift during the move | AC-4 test asserts exact values (300/900, 180/1800) |
| Preflight regressions (it gates every run) | Offline + live preflight runs in Step 7, plus the existing 29 preflight tests |
| Doing this before an unattended run | Explicitly deferred until the 03:05 run drains |

## Rollback

The refactor lands as one commit per step; reverting steps 4–2 in reverse order
restores the old wiring without touching `.env` or the public var names.
