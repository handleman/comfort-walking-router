# 047 Model Config Consolidation — Tasks

Each task is atomic and maps to exactly one acceptance criterion. Implement
**after** the 03:05 unattended run drains (see `spec.md` status).

- [ ] T1 (AC-7, Step 0): `swarm/tests/test_model_config.py::test_checkout_profile_is_unchanged` — pin today's resolved profile (role → model, provider, fallback, crew cap) as a literal; it must pass before and after the refactor.
- [ ] T2 (AC-1): `swarm/model_config.py` — `Role` dataclass + the single `ROLES` table (planner, coder, reviewer, senior, verifier optional, visual, accept, conflict).
- [ ] T3 (AC-2): `model_config.is_free(model)` — the one free predicate; `usage.is_free` and `llms._guard` delegate to it; test asserts agreement on `ollama/*`, `:free`, `-free`, `contributor-free`, paid.
- [ ] T4 (AC-3): `model_config.provider(model)` — the one prefix router; `llms.provider` delegates.
- [ ] T5 (AC-5): `Profile` — `resolve(env)` with `role()`, `paid_allowed`, `crew_timeout()`, `llm_timeout(model)`, `problems()`; CLI `python -m swarm.model_config show`.
- [ ] T6 (AC-4): move the timeout defaults into `Profile` (crew 300/900 cloud/local, per-generation 180/1800) and make `flow._kickoff` + `llms` read them; test asserts exact values and that env overrides still win.
- [ ] T7 (AC-1, AC-3): `llms.ROLE_MODEL_VARS`, `preflight.ROLE_VARS`/`OPTIONAL_ROLE_VARS`, `flow._fallback_key` derived from `ROLES`; test that adding a role to `ROLES` shows up in all four consumers.
- [ ] T8 (AC-6): `Profile.problems()` validates every `*_FALLBACK_MODEL` id (Ollama tags / OpenRouter list / Go catalogue) and pings each provider once; `preflight.check()` delegates to it.
- [ ] T9 (AC-3): `flow._role_provider` reads `Profile.role(...)` (fallback-aware) instead of rebuilding from env.
- [ ] T10 (AC-7): `pytest swarm/tests/ -q` green (774+), `ruff check swarm/` clean, offline + live `python -m swarm.preflight` report 0 problems, `python -m swarm.model_config show` matches T1's golden profile.
- [ ] T11 (AC-7): one real task end-to-end (`make swarm-run SPEC=040 TASK=T13`) still green on the Go profile.
- [ ] T12 (AC-8): `swarm/docs/setup.md` is the single canonical profile section; `AGENTS.md`, `GLOSSARY.md`, `docs/reference.md` reduce to one-line statements + links.
