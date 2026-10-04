# ADR-006: Secrets Handling — Env-Only, Backend-Only

## Context
`008-mapbox-routing` introduces the first secret (`MAPBOX_TOKEN`). Future stages (005 accounts, weather APIs) will add more. One rule must cover all stages. See ADR-002 (token decision), `specs/008-mapbox-routing/spec.md` (AC-2 fail-fast).

## Decision
- Env-only: secrets come from process environment (`MAPBOX_TOKEN`); never config files, never `contracts/`, never specs.
- Backend-only: only `app/` reads secrets; the frontend bundle must contain zero secret references (enforced by grep in CI/review).
- Fail-fast: missing/empty secret aborts backend startup with a clear message naming the var (008 AC-2 pattern for all future secrets).
- Local dev: `.env` (gitignored) + committed `.env.example` with empty placeholders; README-equivalent note in `docs/tech-stack.md` at first secret use.
- Hygiene: no secrets in logs, error messages, snapshots, or spec docs; rotation = new value in env, no code change.

## Alternatives Considered
- Secret manager / vault: robust — deferred (ops overhead for solo MVP; env suffices until multi-env deploys).
- Frontend-proxied key with referrer restrictions: common for maps — rejected (our geometry flows backend-side per ADR-003; no browser key needed).
- Checked-in dev token: convenient — rejected (leak history, quota abuse).

## Consequences
- 008 implements the pattern; every later secret follows it without a new ADR unless the pattern itself changes.
- First-secret change must add `.env.example` + gitignore rule + `tech-stack.md` note (fold into 008 T1).
