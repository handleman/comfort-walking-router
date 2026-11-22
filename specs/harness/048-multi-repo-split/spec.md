# 048 Multi-Repo Split — Spec

Harness spec (control plane; the queue never runs it). This is the concrete
realization of `038-swarm-injection`'s ejectable-release design, plus the
mechanics of splitting one repo into two GitHub products.

## Problem

The dark factory (`swarm/`) and the app it builds (`app/`, `frontend/`,
`tests/`) share one repo, and the factory **hardcodes the app's shape**. A
coupling audit (2026-11-22) found the load-bearing hardcodes:

- `REPO_ROOT = Path(__file__).resolve().parent.parent` in **16 Python modules**
  (`flow`, `prompts`, `tools_guarded`, `preflight`, `acceptance`, `e2e`,
  `report`, `supervise`, `humanlog`, `tui`, `record`, `done`, `crew`,
  `gitpush`, `parallel`, `escape`) and **7 shell scripts** (`run.sh`, `up.sh`,
  `dash.sh`, `db.sh`, `sandbox.sh`, `stop.sh`, `night-run.sh`) — it assumes
  `swarm/` is always a subdirectory of the app repo root.
- The app's shape lives in **5 hardcoded tables**, not a contract:
  `tools_guarded.DEFAULT_SCOPE` (`app/, frontend/, tests/, contracts/…`),
  `SWARM_GATE_COMMANDS` (`pytest, ruff, mypy, npm --prefix frontend…`),
  `gates.DEFAULT_MAP`, `risk.py` class globs, and `flow.HARNESS_SPECS`.
- Three drivers import the app directly: `smoke.py` (`from app import main`),
  `db.sh` (`from app import db`), `acceptance.py` (`uvicorn app.main:app`); the
  rest reference `frontend/` (`e2e.py`, `visual.py`, `preflight` npm checks).
- `specs/harness/` (the factory's own specs, 120 files) and `specs/product/`
  (the app's, 62 files) are interleaved under one `specs/`, and one `AGENTS.md`,
  `GLOSSARY.md`, `changelog.md`, `README.md`, `LICENSE`, `Makefile`,
  `.env.example`, `pyproject.toml` serve both halves.

Two consequences. **(1) Not reusable** — nothing transfers to another app
without editing the harness. **(2) Not releasable** — `specs/harness/038` designed
a PyPI/CLI release, but **zero is implemented**: `swarm/pyproject.toml` is a
dependency-only install (`[tool.setuptools] packages=[]`), there is **no
`[project.scripts]` CLI, no `swarm init`, no `swarm.yaml`**, and the harness
cannot run detached from the app repo.

## Goals — the documented dark-factory product

This split makes the dark factory a **first-class, independently-released product**
named **handleman-hq**, while `comfort-walking-router` becomes a plain app repo.
The factory's standing goals (to be written into its own `README`/mission):

1. **Reusable** — install into *any* app repo and point it at that app via a
   single `swarm.yaml`; the core carries no `app/`, `frontend/`, `tests/` string.
2. **Releasable** — versioned on GitHub (tags + releases), consumed by an app as
   a pin-to-tag dependency. No PyPI (it is a GitHub product, reused across the
   operator's own projects).
3. **Cheap** — cost per *green task*, not per token; free tiers first, honest
   `run.json.cost` (local and `:free` are $0, unpriced paid models are named).
4. **Model-independent** — paid cloud / free cloud / local Ollama / any mix,
   chosen by `.env` only (the profile system from 046/047).
5. **Local-first capable** — Ollama is a first-class, tested profile, not a
   bolt-on; `make swarm-local` and a documented local block.

## Target architecture

```
spec-driven-learn/                    ← plain workspace (no .git)
├── comfort-walking-router/           ← GitHub: handleman/comfort-walking-router  (the app)
│   ├── app/  frontend/  tests/  contracts/  docs/
│   ├── specs/product/*               ← product specs only
│   ├── drivers/                      ← relocated app drivers (smoke, e2e, db, acceptance, visual, bench)
│   ├── swarm.yaml                    ← the target contract (see below)
│   ├── .swarm/                       ← gitignored runtime workspace (runs, plans, journal, ledger)
│   ├── .env.example  Makefile  Dockerfile  render.yaml  pyproject.toml  ...
│   └── AGENTS.md  GLOSSARY.md  README.md  LICENSE
└── handleman-hq/                     ← GitHub: handleman/handleman-hq      (the factory)
    ├── src/swarm/                    ← the dark-factory core (import name stays `swarm`)
    ├── specs/harness/*               ← the factory's own specs (009…047)
    ├── docs/                         ← swarm/docs/* (how-it-works, setup, queue, …)
    ├── examples/                     ← a minimal demo target for `hq init`/tests
    ├── pyproject.toml                ← [project.scripts] hq = "swarm.cli:main"
    └── AGENTS.md  GLOSSARY.md  README.md  LICENSE
```

**Dependency direction:** the app → factory is one-way. The factory is pulled
into the app's harness venv as a git-tag dependency:

```toml
# comfort-walking-router/pyproject.toml (or requirements)
dependencies = ["swarm @ git+https://github.com/handleman/handleman-hq@v0.2.0"]
```

The factory never imports the app, and never knows its repo after `swarm init`
reads `swarm.yaml`.

**Runtime layout (038 §Proposal, confirmed here):** in a target app repo, `hq
init` writes `swarm.yaml` and a gitignored `.swarm/` workspace (runs, plans,
journal, done ledger, approvals, `retry_later`). The factory owns `.swarm/` and
the target files, never its own injected code. The factory's *own* development
state (harness specs, its own tests/bench) lives inside `handleman-hq`, not in a
target.

## Naming & identity (locked)

| Surface | Value | Notes |
| --- | --- | --- |
| Repo / brand | **handleman-hq** | GitHub: `handleman/handleman-hq`, MIT |
| Python import package | **`swarm`** | unchanged — `from swarm import …` across 40 modules / 774 tests |
| CLI (console script) | **`hq`** | `hq run/init/dash/preflight/report/up/stop` |
| Module on disk | `src/swarm/` | src layout; import name stays `swarm` |
| App repo | **comfort-walking-router** | unchanged remote |

## `swarm.yaml` target contract

The single in-repo config the factory reads instead of its hardcoded tables.
Each field names the current hardcode it replaces:

```yaml
# comfort-walking-router/swarm.yaml
specs_dir: specs/product        # spec_loader + flow.HARNESS_SPECS
scope:                          # tools_guarded.DEFAULT_SCOPE + prompt rule
  - app/
  - frontend/
  - tests/
  - contracts/
  - requirements*.txt
  - pyproject.toml
  - swarm.yaml
gates:                          # SWARM_GATE_COMMANDS default + gates.DEFAULT_MAP
  app/**      : "pytest -q; ruff check .; mypy app tests"
  tests/**    : "pytest -q"
  contracts/** : "pytest -q"
  frontend/** : "npm --prefix frontend run check; npm --prefix frontend run lint; npm --prefix frontend test -- --run"
risk:                           # risk.py globs → class
  - [docs/**, 0]
  - [tests/**, 1]
  - [app/**, frontend/src/**, 2]
e2e: 'npm --prefix frontend run test:e2e'   # e2e.py evidence + driver
db:  'DATABASE_URL=… python -c "from app import db"…'  # db.sh migrate
python: '.venv/bin/python'      # how the factory runs app-side Python (gates/acceptance/db)
```

Environment still carries **secrets and the model profile** (keys, model ids,
paid switch, budgets) — the app's `.env` today, unchanged by this spec. The
factory ships its own `.env.example` for the `SWARM_*` keys and `swarm init`
merges the app-agnostic defaults.

## CLI surface (`hq`, first pass)

`hq init` (write `swarm.yaml` + `.swarm/` + gitignore entry), `hq run`
(single task), `hq up`/`hq stop` (background + TUI), `hq dash`, `hq preflight`,
`hq report`, `hq bench`, `hq --version` (reports the git tag). Internal
entry points (`-m swarm.flow`, `-m swarm.tui`) remain for compatibility.

## Migration mechanics (phases)

1. **Greenline gate** — full suite green before any move (app 214+, swarm 774+,
   ruff + mypy clean), committed tag `pre-split`.
2. **History split** — clone, then `git filter-repo --subdirectory-filter swarm/`
   to give `handleman-hq` a clean swarm-rooted history (keeps 475 commits' lessons).
   The app repo keeps its history and simply deletes `swarm/` + `specs/harness/`
   in a normal commit (no force-push of the live remote).
3. **Factory packaging** — src layout, `[project.scripts] hq`, `pip install -e .`
   works in `handleman-hq`'s own venv; `hq --version` prints the tag.
4. **Contract in core** — implement `swarm.yaml` loading; delete the 5 hardcoded
   tables; `REPO_ROOT` becomes "the target repo this `hq` was invoked in".
5. **Driver relocation** — `smoke.py`, `e2e.py`, `db.sh`, the acceptance runner,
   `visual.py`, and `swarm/bench/corpus/` move to the app under `drivers/`
   (invoked via their `swarm.yaml` commands), so the core imports no app code.
6. **App wiring** — add `swarm.yaml`, gitignore `.swarm/`, the git-tag dependency,
   split the Makefile; split `.env.example` (app keys vs `SWARM_*`).
7. **Docs/specs split** — factory gets its own `AGENTS.md`, `GLOSSARY.md`,
   `README.md`, `LICENSE`, `docs/`; app keeps product `docs/`, `specs/product/`,
   and its own `AGENTS.md`.
8. **Release** — tag `v0.2.0` in `handleman-hq`, `gh release create`, app pins
   `@v0.2.0`; verify `make test`, `make e2e`, `hq run` on a real task.

## Product-specific driver disposition

| Today | Moves to | Driven by |
| --- | --- | --- |
| `swarm/smoke.py` | `comfort-walking-router/drivers/smoke.py` | `hq smoke` (app driver) |
| `swarm/e2e.py` + `e2e_guard.py`/`e2e_triage.py` | `…/drivers/e2e.py` | `swarm.yaml.e2e` |
| `swarm/db.sh` | `…/drivers/db.sh` | `swarm.yaml.db` |
| `swarm/acceptance.py` (app parts) + `frontend/scripts/acceptance.mjs` | `…/drivers/acceptance.py` | `hq accept` |
| `swarm/visual.py` | `…/drivers/visual.py` | `hq accept` (vision step) |
| `swarm/bench/corpus/` (frozen app history) | `…/drivers/bench-corpus/` | `hq bench` |

The factory core (flow, crew, gates, guards, llms, spec_loader, usage, journal,
supervise, tui, preflight-minus-app-checks) stays app-agnostic.

## Shared-root file disposition

| File | comfort-walking-router | handleman-hq |
| --- | --- | --- |
| `Makefile` | app targets + a `hq` passthrough | its own (dev/test/release) |
| `.env.example` | app keys (MAPBOX, DATABASE_URL) | `SWARM_*` keys only |
| `AGENTS.md` / `GLOSSARY.md` / `README.md` / `LICENSE` | app copy | factory copy (MIT) |
| `pyproject.toml` | app deps + ruff/mypy | package metadata + `[project.scripts]` |
| `docs/` | product `docs/*`, runbooks, research→factory? | `swarm/docs/*` |
| `changelog.md` | app changelog | split (factory keeps harness entries) |
| `.specify/` templates | both (thin authoring templates) | both |
| `contracts/`, `cache/`, `test-results/`, `openrc.json` | app | — |
| `Dockerfile`, `render.yaml`, `.dockerignore` | app | — |

## Secrets & publication hygiene

Before any public push: `.env` (real keys), `cache/*.db`, `swarm/runs/` (run
traces, prompts, some logs), `test-results/`, venvs, and `*.egg-info/` are all
gitignored — confirm none is tracked in the filtered factory history (the old
commits predate some gitignore entries; a `git log --all-match`/secret scan pass
runs before pushing `handleman-hq`). Repo is MIT, holder "Poul Handleman".

## Technologies (multi-repo tooling)

- **`git filter-repo`** (brew install) — subtree history split; both halves get a
  clean, pushable history.
- **GitHub releases + `gh` CLI** — `gh repo create handleman/handleman-hq --public
  --license mit`, `gh release create v0.2.0`.
- **pip git-tag dependency** — `swarm @ git+…@vX.Y.Z` (no PyPI).
- **src layout + build backend** — `hatchling` (or setuptools) with
  `[project.scripts]`; `hq` as the console entry point.
- **`.swarm/` target workspace** — gitignored per-target runtime state.
- **Two venvs** — the factory's own dev venv in `handleman-hq`; the app's harness
  venv holds the installed `hq`.

## Non-goals

- No PyPI / no hosted SaaS (GitHub releases only).
- No rewrite of the flow/crew/guards internals.
- No `.github` CI in this pass (releases are `gh release create`; CI is follow-up).
- No renaming of the `swarm` import package or the app's internal modules.

## Acceptance criteria

- **AC-1 (two repos)** — `comfort-walking-router` and `handleman-hq` are independent
  git repos under the workspace; the app has no `swarm/` or `specs/harness/`, the
  factory has no `app/`, `frontend/`, `tests/`, `specs/product/`.
- **AC-2 (factory history)** — `handleman-hq` history is the swarm subtree
  (filter-repo), not a squash; `git log -- swarm/flow.py` in the factory traces
  back to ≥ the 009 harness commits.
- **AC-3 (installable)** — `pip install -e .` in `handleman-hq` exposes `hq`;
  `hq --version` reports the tag; `hq init` on a fresh dir writes `swarm.yaml` +
  `.swarm/`.
- **AC-4 (contract)** — the core reads `swarm.yaml` for specs_dir/scope/gates/
  risk/e2e/db/python; no `app/`, `frontend/`, `tests/`, `contracts/` string remains
  in the factory core (verified by grep).
- **AC-5 (drivers out)** — `smoke/e2e/db/acceptance/visual/bench-corpus` live in
  the app; the factory core imports no app code (`grep "from app\|import app"` clean).
- **AC-6 (app still green)** — `make test` and `make e2e` pass in the app; a real
  `hq run` task (e.g. 040-T13) reaches green on the git-tag dependency.
- **AC-7 (factory green)** — `pytest` in `handleman-hq` passes (774+ unit tests,
  now under `tests/`); `ruff check` and `mypy` clean.
- **AC-8 (docs/specs split)** — each repo has its own `AGENTS.md`, `GLOSSARY.md`,
  `README` and `LICENSE`; factory docs cover the cheap/model-independent/
  local-Ollama goals; harness specs live in `handleman-hq/specs/harness/`, product
  specs in `comfort-walking-router/specs/product/`.
- **AC-9 (released)** — `handleman-hq` has a `v0.2.0` GitHub release; the app's
  dependency pins that tag.

## Success definition

`gh repo create handleman/handleman-hq` produces a repo whose `hq init` + `hq run`,
installed as `git+…@v0.2.0` into `comfort-walking-router`, plans/codes/verifies/
commits a task there with no app string in the factory core — and
`comfort-walking-router` builds its own Docker/Render app exactly as before, only
now depending on a separately versioned, reusable dark factory.