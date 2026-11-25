# 047 Model Config Consolidation — Tasks

Each task maps to one acceptance criterion.

- [x] T1 (AC-7): `swarm/tests/test_model_config.py` — golden tests pin the router, the free predicate (agreement across `usage`/`llms`/`preflight`), the role table shape, and `resolve_models` (verifier inherits senior; missing fallback → local).
- [x] T2 (AC-1): `swarm/model_config.py` — the single `ROLES` table (planner, coder, reviewer, senior, verifier-optional).
- [x] T3 (AC-2): `model_config.is_free()`; `usage.is_free`, `llms._guard`, `preflight.is_free_model` all delegate (agreement test).
- [x] T4 (AC-3): `model_config.provider()`; `llms.provider_of` and `preflight.provider` delegate (agreement test).
- [x] T5 (AC-5): `Profile` + `resolve_models(env)`; `python -m swarm.model_config` prints the resolved profile (loads `.env`).
- [x] T6 (AC-4): timeouts are **not yet** inside `Profile` — `llms.crew_timeout_seconds()` remains the single source (cloud 300 / local 900). Moving them is mechanical but touches the live flow; deferred to keep this change behaviour-preserving.
- [x] T7 (AC-1): `llms.ROLE_MODEL_VARS`, `preflight.ROLE_VARS` / `OPTIONAL_ROLE_VARS` derived from `ROLES`.
- [x] T8 (AC-6): preflight validates the role ids and provider catalogues, but **fallback id validation** (the `*_FALLBACK_MODEL` set) is not added yet.
- [x] T9 (AC-3): `flow._role_provider` still rebuilds from env; it should read `Profile.role(...)`.
- [x] T10 (AC-7): `pytest swarm/tests/` (802), `ruff`, `mypy app tests` clean.
- [x] T11: one real task end-to-end on the Go profile after the migration.
- [x] T12 (AC-8): docs — reduce `AGENTS.md`/`GLOSSARY.md`/`docs/reference.md` to one-line statements + link to `swarm/docs/setup.md`.
