# 048 Multi-Repo Split — Tasks

Each task maps to one acceptance criterion or a phase boundary. Execute in
order; every phase ends green.

## Phase 0 — greenline
- [ ] T1 (AC-0): `git tag pre-split`; `git status --short` empty; `make test` (214), `make e2e`, `pytest swarm/tests/` (774), `ruff check .`, `mypy app tests` all green.
- [x] T2 (AC-0): `brew install git-filter-repo` (2.47.0); `git bundle create /tmp/comfort-full-20261125.bundle --all` (1.7 MB).

## Phase 1 — history split
- [x] T3 (AC-2): `git clone . /tmp/hq-src && git filter-repo --subdirectory-filter swarm/` → 228 commits, swarm-rooted, app/frontend/specs/product gone, 047/050/052 commits present. Verified (throwaway; the real repo is created in Phase 7).
- [x] T4 (AC-0): secret scan the filtered history — 0 hits for the four real key/token values, 0 `.env`-shaped assignments, no `.env` ever committed (2026-11-26, `git log --all -p | grep -F -f <values>` + name scan).

## Phase 2 — factory packaging
- [x] T5 (AC-3): `src/swarm/` core + `handleman-hq` pyproject (hatchling, `hq = swarm.cli:main`) done in `/tmp/hq-src2` (branch from `1c2d691`); `bench/` moved in; `swarm/paths.py` is the one `REPO_ROOT` (`SWARM_TARGET` else checkout). Test triage 56 → 21 failures; the rest need T5b/T9/T11.
- [x] T6 (AC-3): `swarm/cli.py` implements `--version/init/run/preflight/report/bench` and `up/stop/dash` (queue scripts); `PYTHONPATH=src python -m swarm.cli --version` → `hq 0.2.0`; `hq init` writes `swarm.yaml`. `pip install -e .` still to verify.
- [x] T7 (AC-7): factory suite green — **833 passed, 8 skipped** in the filtered layout; `pytest -m "not driver"` passes with no `app/`; ruff clean after the src-layout config. (`pip install -e .` still to verify in a fresh venv.)

### Discovered — T5b (blocks T7)

- [x] T5b: split the tests that assert on a *target repo* from the ones that test the
  *core*. The factory must pass with no `app/`, `frontend/`, `specs/product/` or
  `Makefile`: `corridor_check`/`bench live`/`baseline` are drivers (T11), and tests
  that read `specs/product/028-*`, `swarm/bench/...` or `swarm/<script>.sh` need
  fixtures or a `pytest.mark.driver`. 21 remaining: 3 autoloop (branch/scope
  strings), 2 bench_live + 2 replay (factory `Makefile`), 3 corridor_check (app
  import), 4 prompts + 1 progress (spec fixtures), 2 sandbox (script paths),
  3 search (source root), 1 gates/qa shell (PATH), 1 tui (spec dir name).

## Phase 3 — contract in core
- [x] T8 (AC-4): `swarm/contract.py` loads `swarm.yaml` (specs_dir/scope/gates/risk/e2e/db/python) with defaults reproducing today's behaviour.
- [~] T9 (AC-4): **consumers wired** in `/tmp/hq-src3` — scope, affected-gate map, gate commands, risk classes and harness specs read `swarm.yaml` (env still wins); `paths._default_root()` falls back to cwd for an installed package. **Defaults stay app-shaped** until the app ships its own `swarm.yaml` (Phase 5): switching them to generic (`src/`, `tests/`) turns **30 factory tests red**, all encoding the app's scope — the same core/app split as T5b, now for contracts. See T9b.
- [ ] T9b (AC-4, discovered 2026-11-26): make the scope/risk tests contract-aware — they assert the app's paths (`app/`, `frontend/`) from `resolve_scope()`/`risk.classify`, so generic factory defaults fail them. Load the target's `swarm.yaml` in a fixture (or mark them `driver`), then T9 can drop the app-shaped defaults and T10's grep can pass.
- [ ] T10 (AC-4): verify `grep -rn "app/|frontend/|tests/|contracts/" src/swarm/` clean for the core (drivers excluded).

## Phase 4 — driver relocation
- [ ] T11 (AC-5): move `smoke.py`, `e2e.py`, `e2e_guard.py`, `e2e_triage.py`, `db.sh`, `acceptance.py`, `visual.py`, `bench/corpus/` → `comfort-walking-router/drivers/`; wire via `swarm.yaml` (`e2e`, `db`, acceptance/vision).
- [ ] T12 (AC-5): verify `grep "from app\|import app" src/swarm/` clean.

## Phase 5 — app wiring
- [ ] T13 (AC-1): delete `swarm/` + `specs/harness/` from the app repo (history preserved); add `swarm.yaml`, `.swarm/` gitignore.
- [ ] T14 (AC-6): app `pyproject.toml`/Makefile depend on `swarm @ git+…@v0.2.0`; split `Makefile` + `.env.example`.

## Phase 6 — docs/specs/AGENTS split
- [~] T15 (AC-8): factory `README` (cheap/model-independent/local-Ollama goals), `AGENTS.md`, `GLOSSARY.md`, `LICENSE`, `docs/`, `specs/harness/*`, `.specify/` templates.
- [ ] T16 (AC-8): app `AGENTS.md`, `GLOSSARY.md`, `README`, `docs/*`, `specs/product/*`, `.specify/` templates.

## Phase 7 — release + verify
- [x] T17 (AC-9): `gh repo create handleman/handleman-hq --public --license mit`; push filtered `main`.
- [x] T18 (AC-9): tag `v0.2.0`; `gh release create v0.2.0`.
- [ ] T19 (AC-6, AC-7): app installs `swarm @ git+…@v0.2.0`; `make test` + `make e2e` green; one real `hq run` task (040-T13) green; factory `pytest` green.

## Verify
- [ ] T20 (AC-1…AC-9): full AC pass — two independent repos under the workspace, factory history preserved, `hq` installable + `--version`, app agnostic (`grep` clean), drivers relocated, both suites green, docs/specs split, `v0.2.0` released and pinned.