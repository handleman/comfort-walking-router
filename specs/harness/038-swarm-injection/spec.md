# 038 Swarm Injection & Release — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The swarm and the app it builds share one repo, and the swarm *hardcodes* the
app's shape. Today's coupling points:

- `swarm/tools_guarded.py::DEFAULT_SCOPE` — `app/, frontend/, tests/,
  contracts/, requirements*.txt, pyproject.toml, .gitignore`.
- `swarm/risk.py` — risk classes keyed to `app/`, `frontend/src/`,
  `contracts/`, `swarm/`, `specs/`, `migrations`.
- `swarm/prompts.py` — the scope rule tells the coder "Touch ONLY files under
  app/, frontend/, tests/, contracts/…".
- Gates — `pytest`, `ruff`, `mypy`, `npm --prefix frontend run …` (validators
  and `SWARM_GATE_COMMANDS` both assume a Python + Svelte/npm app).
- `swarm/e2e.py`, `swarm/smoke.py`, `swarm/db.sh` — product-specific (Playwright
  suite, Overpass/Mapbox live smoke, the `comfort-pg` Postgres).
- `swarm/bench/corpus/` — frozen cases of *this* app's history.
- `specs/` at the repo root; `HARNESS_SPECS` names this project's harness specs.
- `REPO_ROOT = Path(__file__).resolve().parent.parent` — assumes `swarm/` and
  the product are siblings under one root.

Two concrete symptoms. (1) **No reuse**: nothing here transfers to another app
without editing the harness. (2) **The harness edits itself out of the way**: on
2026-11-21 the 036-T1 run reverted my `swarm/tools_guarded.py` `npx` change as
"out-of-scope", because `swarm/` is outside the coder's own scope — the tool and
the target are the same tree, so the swarm and the product interfere.

## Goal

The swarm becomes a **separate, injectable, releasable tool**: a `swarm` package
+ CLI that can be dropped into *any* app repo, where it has full authority over
the app's own folder (the **target**) and never touches its own code. Reusable
for other app builds, versioned and distributed like any tool.

## Investigation

### How similar harnesses ship (2026)

| Tool | Ship model | In-repo config |
| --- | --- | --- |
| CrewAI | pip package + `crewai create` CLI | `pyproject.toml`/agent files |
| Aider | pip + `aider` CLI | `.aider.conf.yml` |
| Claude Code | npm package + `claude` CLI | `.claude/`, settings.json |
| OpenHands | Docker + pip | `config.toml` |

The pattern is uniform: **a package + a CLI, and the target repo declares its
own shape in a config file** — the tool knows nothing hardcoded about the app.

### Injection options

| Option | How | Verdict |
| --- | --- | --- |
| **pip package + `swarm` CLI** | `pip install swarm-harness`; `swarm init` in the app repo | ✅ primary — the standard pattern |
| Git submodule | `swarm/` as a submodule | ❌ clunky, no version isolation |
| Vendored copy | `swarm init` copies the harness into `.swarm/` | ⚠️ fallback for air-gapped/no-pip |
| Docker image | container mounts the app repo | ⚠️ heavy; keep as an option, not the default |

### Release options

- **PyPI** (`swarm-harness`) + `swarm --version` / semver tags — the default.
- **GitHub releases** + a `swarm init` that pins a release tag.
- A **template repo** for the target side (`app-skeleton`) — optional starter.

## Proposal

1. **Split `swarm/` out of the product repo** into its own package/repo. The
   product becomes a plain app repo the swarm is *pointed at*.
2. **`swarm.yaml` (target contract).** The app repo declares, in one file:
   - `specs_dir` (where `specs/` lives; `product`/`harness` kind rule),
   - `scope` (the prefixes the coder may write — *the target's whole folder*),
   - `gates` (the verification commands),
   - `risk` (class → path globs), `e2e` (the browser-suite command), `db`
     (optional datastore), `models` (routing prefix/env).
   The harness reads this instead of hardcoding `app/, frontend/, tests/`.
3. **`swarm init`** generates `swarm.yaml` from a template and creates the
   `.swarm/` workspace (runs, plans, journal, corpus) *inside the target repo*,
   gitignored — the swarm owns `.swarm/` and the target, never `swarm/` itself.
4. **Release** via PyPI + GitHub releases/tags; `swarm` CLI is the entry point
   (`swarm run`, `swarm up`, `swarm dash`, `swarm preflight`, `swarm report`).
5. **Product-specific bits move to the target as plugins/contracts**, not the
   swarm core: the Overpass/Mapbox smoke, the Playwright e2e driver, the Postgres
   helper, and the comfort scoring all describe *this* app, so they live with the
   app (or behind the `swarm.yaml` gates), leaving the swarm core app-agnostic.

## Non-goals

- Re-architecting the flow/crews/guards themselves (that stays).
- A hosted/SaaS swarm (still a local CLI, cloud models optional).

## Acceptance criteria (future implementation)

- **AC-1 — Separable.** `swarm/` imports nothing app-specific; the app repo
  works with `pip install swarm-harness && swarm init && swarm run`.
- **AC-2 — Target contract.** `swarm.yaml` is the single source of scope, gates,
  risk, e2e and spec dir; the harness has no `app/`, `frontend/`, `tests/`,
  `contracts/` string in its core.
- **AC-3 — Own-folder authority.** The coder's scope is the target's folder; the
  swarm never edits or reverts its own injected files.
- **AC-4 — Releasable.** `swarm` is versioned (semver), `swarm init` pins a
  release, and `swarm --version` reports it.
- **AC-5 — This repo still builds.** The current product (comfort route guide)
  migrates onto the new model without losing green: `make test`, `make e2e`,
  `make swarm-test` still pass.

## Success definition

`pip install swarm-harness` in a fresh, empty app repo, one `swarm.yaml`, and
`swarm run` plans, codes, verifies and commits a task there — with the comfort
route guide as the first migrated customer and no product string left in the
swarm's core.
