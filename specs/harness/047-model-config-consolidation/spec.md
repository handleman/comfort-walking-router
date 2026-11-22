# 047 Model Config Consolidation — Spec

Harness spec (control plane; the queue never runs it).

**Status:** designed 2026-11-22, implementation deliberately deferred until the
03:05 unattended run drains (it touches `llms`/`flow`/`preflight`, which a live
run depends on).

## Problem

Model configuration knowledge is spread across four modules and duplicated
inside each. None of the duplications is a feature; each is a place where two
sources of truth can drift, and two already did:

1. **Free-model predicate, written twice.** `swarm/llms.py::_guard` inlines
   `:free` / `ollama/` / `-free` / `contributor-free`; `swarm/usage.py::is_free`
   repeats the same rules. Cost accounting and the paid guard can disagree.
2. **Role list, declared four times.** `llms.ROLE_MODEL_VARS`,
   `preflight.ROLE_VARS`, `preflight.OPTIONAL_ROLE_VARS` (verifier),
   `flow._fallback_key` (role → env var). Adding a role means editing four
   places, and a missed one fails silently (the verifier was absent from
   preflight until 2026-11-22).
3. **Provider detection, re-derived three times.** `llms.provider()` (prefix →
   provider), `preflight._ping_model_ids` (per-provider branches), and
   `flow._role_provider` (rebuilds the model from env + fallback state).
4. **Timeout derivation, scattered.** `llms.crew_timeout_seconds()` (profile →
   300/900), `llms._fix_timeout()` / `_build` (per-generation, with a separate
   Ollama value), `flow._check_wall_budget` (task budget), and
   `SWARM_MAX_SECONDS_PER_TASK`. Four rules answer "which cap applies?", in
   three modules.
5. **Policy split by module.** Paid allowed (`llms`), free-only preflight check
   (`preflight`), price knowledge (`usage`), vision capability (nowhere — it is
   implicit in the model id).

Two production incidents came from exactly this shape:

- a **dead fallback id** (`opencode-go/qwen3.8-flash`) sat in
  `SWARM_LOCAL_FALLBACK_MODEL` as if it were an OpenRouter model, because
  nothing validated fallbacks;
- a **cloud-sized crew cap** would have truncated every local step, because the
  cap's default lived in `.env` rather than being derived from the profile.

## Goal

One resolver owns the knowledge; every consumer asks it. **The operator-facing
surface does not change** — the same env var names, the same `.env` files, the
same `make swarm-local`, the same docs examples. What changes is *where* the
knowledge lives and how many copies exist.

```
swarm/model_config.py
    ROLES = (Role("coder", "SWARM_CODER_MODEL", "SWARM_CODER_FALLBACK_MODEL", vision=False), …)
    resolve(env) -> Profile
    Profile.role("coder")      -> Model(id, provider, free, vision, fallback)
    Profile.paid_allowed       -> bool
    Profile.crew_timeout()     -> float          # local 900 / cloud 300, one rule
    Profile.llm_timeout(model) -> int            # per generation, one rule
    Profile.problems()         -> list[Problem]  # what preflight reports
```

`llms`, `flow`, `preflight`, `usage` and the dashboard read that object. The
prefix router and the free predicate exist once.

## Non-goals

- No new env var names, no `.env` migration, no behaviour change for a healthy
  profile (a run before/after this spec must resolve identical models and caps).
- No config file format (TOML/YAML) — env stays the interface.
- No provider registry/plugin system; three prefixes are enough.
- Not a rewrite of `llms.py`: the builders stay, they just read `Profile`.

## Acceptance Criteria

- [ ] **AC-1 (one role table):** exactly one declaration of the role set exists
      (`model_config.ROLES`); `llms.ROLE_MODEL_VARS`, `preflight.ROLE_VARS` /
      `OPTIONAL_ROLE_VARS` and `flow._fallback_key` are derived from it, and a
      test asserts a new role added there appears in all four consumers.
- [ ] **AC-2 (one free predicate):** `usage.is_free` and `llms._guard` call the
      same function; a test asserts they agree for `ollama/*`, `:free`,
      `-free`, `contributor-free` and a paid id.
- [ ] **AC-3 (one router):** provider detection exists once; `flow._role_provider`
      and `preflight`'s catalogue pings use it (no second prefix table).
- [ ] **AC-4 (one timeout rule):** `Profile.crew_timeout()` and
      `Profile.llm_timeout(model)` are the only places a timeout default is
      decided; `flow` and `llms` call them. Cloud 300 s / local 900 s and the
      per-generation cloud/local split keep their current values.
- [ ] **AC-5 (profile is inspectable):** `python -m swarm.model_config show`
      prints the resolved profile (role, model, provider, free/paid, vision,
      fallback, effective caps) from `.env` — the same object the run uses, so
      the dashboard, preflight and docs cannot disagree with it.
- [ ] **AC-6 (fallbacks are validated):** preflight checks every
      `*_FALLBACK_MODEL` id against its provider (Ollama tags / OpenRouter list /
      Go catalogue), not just the five role ids — the dead-fallback class of bug
      fails in seconds.
- [ ] **AC-7 (no behaviour change):** `pytest swarm/tests/ -q` green (774+), and
      a golden test resolves the checkout's `.env` to the same models/caps before
      and after the refactor.
- [ ] **AC-8 (docs collapse):** `AGENTS.md`, `GLOSSARY.md` and
      `docs/reference.md` state the contract in one line and link to
      `swarm/docs/setup.md`; the profile rules are written once, in setup.md.

## Files

- `swarm/model_config.py` (new) — roles, router, free predicate, `Profile`.
- `swarm/llms.py` — builders read `Profile`; `_guard`/`_paid_ok` use it.
- `swarm/preflight.py` — validates `Profile.problems()`; drops its own role list
  and per-provider branches.
- `swarm/flow.py` — `_fallback_key`/`_role_provider`/crew cap read `Profile`.
- `swarm/usage.py` — imports the shared free predicate.
- `swarm/tests/test_model_config.py` (new) + touched consumer tests.
- `swarm/docs/setup.md` (canonical), `AGENTS.md`, `GLOSSARY.md`,
  `docs/reference.md` (links).
