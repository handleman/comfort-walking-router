# AGENTS.md

Learning repo for spec-driven development + swarming agents. The **comfort route
guide** lives in `app/` and `frontend/` — a walking app that scores routes by
comfort from real OSM data, with a live GPS walk mode.
Live: https://comfort-walking-router.onrender.com/

The **harness** that builds it is the published
[**handleman-hq**](https://github.com/handleman/handleman-hq) package (pinned
`v0.6.7`), installed in `harness/.venv`. This repo no longer vendors the harness.

## State (essentials)

- **Specs are the source of truth:** `spec.md` → `plan.md` → `tasks.md` under
  `specs/product/` (the queue runs them). `specs/harness/` is this repo's
  historical harness record — it is **not** queued and new harness work belongs in
  the factory repo. Templates in `.specify/templates/`.
- **Drivers live in `drivers/`:** the target declares `drivers.{e2e,db}` in `swarm.yaml` as
  JSON-speaking commands (056); the packaged implementation is the fallback.
- **The contract is `swarm.yaml`:** specs dir, scope, gates (+ affected gate map),
  e2e command/spec root, risk classes, db script, `python.venv` and `runs_dir`.
  The harness reads it; don't hardcode paths elsewhere.
- **The queue is autonomous:** a green run merges by itself. Runs and traces live
  in `harness/runs/`.
- **Separate venvs:** `app/`+`tests/` → `.venv`, harness → `harness/.venv`,
  `frontend/` → npm. Don't mix them.
- **Commands:** `hq` (the harness entry point) or `make swarm-*`. `make
  swarm-health` proves the stand; `make swarm-accept` is the final greenlight.

## Spec-driven workflow (the rules)

- **Route requests by target.** A request about the *built app* goes to the
  **queue**: write `spec.md` + `plan.md` + `tasks.md` under `specs/product/…` and
  let the queue implement it. A request to *change the harness itself* (roles,
  guards, verification) goes to the **factory repo** with its own spec. Only
  small, isolated direct edits (a one-line fix) bypass the spec step.
- **Clarify by grilling first.** Iteratively question the user until the picture
  is unambiguous — goal, scope, priorities, edge cases, anything interpretable two
  ways. Do not guess.
- **Spec before code.** Requirements, acceptance criteria and scope in `specs/`
  first; one task maps to one AC.
- **Visual-check UI in the built-in browser.** A map can render no tiles while
  tests pass; check desktop and mobile sizes and look at the screenshot.
- **Live-only ACs.** The strict pass is hermetic (`ROUTE_FIXTURES=1`, no DB);
  ACs that need the real Mapbox provider, Postgres, or the Render deployment
  declare `live.toml` and are checked by `make accept-live` (writes
  `acceptance-live.md`; DB specs skip when Postgres is down). Never fake them in
  the strict stand.
- **Final greenlight.** `make swarm-accept` (043) checks every built product spec
  in a real browser against its ACs (desktop + mobile). Failures append `T<n>` fix
  tasks back to `tasks.md` and exit non-zero; `--selftest` also proves the oracle
  can fail, `--strict` makes an AC without a check fatal. The supervisor runs the
  per-feature acceptance pass after every green feature task.
- **Update tasks/ACs in the same change** as the implementation; record completed
  work and blockers explicitly. Prefer editing existing files; keep changes
  minimal. Do not invent commands — verify via `Makefile`/`swarm.yaml`.
- **Model profiles are configuration, not capability.** One source of truth is
  the harness (`swarm.model_config`, consumed by `swarm.llms`); only `.env`
  changes. `hq preflight` validates every id *and every fallback*. **Judgement
  roles need a reasoning model** — cheap models are for mechanical work (a
  cheapest-tier reviewer once blocked a green task with no evidence; a reasoning
  reviewer later blocked a wrong fix with a precise reason). Full rules:
  [model-usage](https://github.com/handleman/handleman-hq/blob/main/docs/model-usage.md)
  and [setup](https://github.com/handleman/handleman-hq/blob/main/docs/setup.md).
- **Swarm Agent Skills:** operators add behaviour via YAML-frontmatter files under
  `harness/agents/skills/<role>.md`; the harness auto-discovers them (additive).
  `SWARM_SKILLS=0` disables, `SWARM_SKILLS_DIR` relocates.

## Where to find more (load on demand)

- **Terms:** [GLOSSARY.md](GLOSSARY.md); the factory's language and domain model:
  [GLOSSARY](https://github.com/handleman/handleman-hq/blob/main/GLOSSARY.md),
  [domain model](https://github.com/handleman/handleman-hq/blob/main/docs/domain-model.md),
  [ADRs](https://github.com/handleman/handleman-hq/tree/main/docs/adr).
- **Skills:** the `skill` tool (`domain-modeling`, `grilling`, `browser`, …).
- **Harness docs (factory):** [README](https://github.com/handleman/handleman-hq#readme),
  [how it works](https://github.com/handleman/handleman-hq/blob/main/docs/how-it-works.md),
  [run guards](https://github.com/handleman/handleman-hq/blob/main/docs/run-guards.md),
  [lessons](https://github.com/handleman/handleman-hq/blob/main/docs/lessons.md).
- **Commands & boundaries:** [docs/reference.md](docs/reference.md).
- **Figma:** [docs/figma.md](docs/figma.md) — OpenCode MCP lane (operator) and the
  cached design lane for the queue (factory spec 057).
- **Runbooks:** [docs/runbooks/](docs/runbooks/) — local-postgres, e2e-suite,
  verification, deploy, overnight-runs.
- **This repo's harness history:** [specs/harness/ROADMAP.md](specs/harness/ROADMAP.md)
  — the record of how the factory was built (the work itself now lives upstream).
