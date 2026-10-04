# ADR-010: Dev-CI Environment — Python + Node + Postgres

## Context
The stack spans two toolchains (Python backend, Node/Svelte frontend) plus Postgres from 005. Dev and CI must reproduce the same services with minimal setup. See ADR-004/ADR-007 (Postgres), `docs/tech-stack.md` (proposed commands).

## Decision
- Dev: `python -m venv` + `pip install` (backend), `npm install` in `frontend/` (Vite/Svelte/TS), Postgres via container, `.env` (gitignored) + `.env.example` per ADR-006.
- CI mirrors dev: Python test/lint/type (`pytest`, `ruff`, `mypy`), frontend check/tests (`npm run check`, unit), Postgres service for 005 suite; SQLite-only tests need no service.
- Service split: anything needing Postgres is marked and isolated so backend-pure and frontend suites run without it.
- Commands in `docs/tech-stack.md` become verified (drop "proposed") once manifests land and CI runs green once.

## Alternatives Considered
- Single-toolchain (SSR only): one runtime — rejected with Svelte decision (ADR-003).
- Postgres everywhere incl. cache: uniform — rejected (ADR-004: SQLite keeps ephemeral cache).
- Remote shared dev DB: convenient — rejected (state bleed between developers; local container instead).

## Consequences
- 001 T1 scaffold must land manifests + service definitions; `AGENTS.md`/`tech-stack.md` updated to verified commands at that point.
- New services in later stages need their ADR + CI wiring, not ad-hoc docs.
