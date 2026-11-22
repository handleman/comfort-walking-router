# 048 Multi-Repo Split — Tasks

Each task maps to one acceptance criterion or a phase boundary. Execute in
order; every phase ends green.

## Phase 0 — greenline
- [ ] T1 (AC-0): `git tag pre-split`; `git status --short` empty; `make test` (214), `make e2e`, `pytest swarm/tests/` (774), `ruff check .`, `mypy app tests` all green.
- [ ] T2 (AC-0): `brew install git-filter-repo`; `git bundle create /tmp/comfort-full.bundle --all`.

## Phase 1 — history split
- [ ] T3 (AC-2): in a clone, `git filter-repo --subdirectory-filter swarm/` → `swarm/` rooted history for `handleman-hq`; verify `git log -- swarm/flow.py` traces to the 009 harness commits.
- [ ] T4 (AC-0): secret scan the filtered history (real `OPENROUTER_API_KEY` / `OPENCODE_API_KEY` / `MAPBOX_TOKEN` values); clean before any push.

## Phase 2 — factory packaging
- [ ] T5 (AC-3): `handleman-hq/pyproject.toml` — name `handleman-hq`, import `swarm`, `hatchling` backend, `[project.scripts] hq = "swarm.cli:main"`; move core to `src/swarm/`.
- [ ] T6 (AC-3): `swarm/cli.py` with `init/run/up/stop/dash/preflight/report/bench/--version`; `pip install -e .` exposes `hq`; `hq --version` prints the tag.
- [ ] T7 (AC-7): factory unit tests under `tests/` pass (774+); `ruff` + `mypy` clean in `handleman-hq`.

## Phase 3 — contract in core
- [ ] T8 (AC-4): `swarm/contract.py` loads `swarm.yaml` (specs_dir/scope/gates/risk/e2e/db/python) with defaults reproducing today's behaviour.
- [ ] T9 (AC-4): delete the 5 hardcoded tables; `REPO_ROOT` → target repo `hq` was invoked in (back-compat cwd default for `-m swarm.*`).
- [ ] T10 (AC-4): verify `grep -rn "app/|frontend/|tests/|contracts/" src/swarm/` clean for the core (drivers excluded).

## Phase 4 — driver relocation
- [ ] T11 (AC-5): move `smoke.py`, `e2e.py`, `e2e_guard.py`, `e2e_triage.py`, `db.sh`, `acceptance.py`, `visual.py`, `bench/corpus/` → `comfort-walking-router/drivers/`; wire via `swarm.yaml` (`e2e`, `db`, acceptance/vision).
- [ ] T12 (AC-5): verify `grep "from app\|import app" src/swarm/` clean.

## Phase 5 — app wiring
- [ ] T13 (AC-1): delete `swarm/` + `specs/harness/` from the app repo (history preserved); add `swarm.yaml`, `.swarm/` gitignore.
- [ ] T14 (AC-6): app `pyproject.toml`/Makefile depend on `swarm @ git+…@v0.2.0`; split `Makefile` + `.env.example`.

## Phase 6 — docs/specs/AGENTS split
- [ ] T15 (AC-8): factory `README` (cheap/model-independent/local-Ollama goals), `AGENTS.md`, `GLOSSARY.md`, `LICENSE`, `docs/`, `specs/harness/*`, `.specify/` templates.
- [ ] T16 (AC-8): app `AGENTS.md`, `GLOSSARY.md`, `README`, `docs/*`, `specs/product/*`, `.specify/` templates.

## Phase 7 — release + verify
- [ ] T17 (AC-9): `gh repo create handleman/handleman-hq --public --license mit`; push filtered `main`.
- [ ] T18 (AC-9): tag `v0.2.0`; `gh release create v0.2.0`.
- [ ] T19 (AC-6, AC-7): app installs `swarm @ git+…@v0.2.0`; `make test` + `make e2e` green; one real `hq run` task (040-T13) green; factory `pytest` green.

## Verify
- [ ] T20 (AC-1…AC-9): full AC pass — two independent repos under the workspace, factory history preserved, `hq` installable + `--version`, app agnostic (`grep` clean), drivers relocated, both suites green, docs/specs split, `v0.2.0` released and pinned.