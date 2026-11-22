# 048 Multi-Repo Split — Plan

References `specs/harness/048-multi-repo-split/spec.md` AC-1–AC-9.

## Approach

Behaviour-preserving, phase-ordered, reversibly committed. Every phase ends in a
green line so a regression is a phase boundary, not a mystery. The one
irreversible surface — the public `handleman-hq` remote — is created last, only
after the history split and a secret scan pass.

## Phase 0 — Greenline + tooling

- Confirm `git status` clean, both venvs green and full suites pass
  (`make test`, `make e2e`, `pytest swarm/tests/`, ruff, mypy).
- Tag the pre-split state: `git tag pre-split`.
- `brew install git-filter-repo`.
- Backup: `git bundle create /tmp/comfort-full.bundle --all` (off-repo safety).

## Phase 1 — History split (two clean histories)

- `git clone . /tmp/hq-src` (a clone for surgery; never operate on the live repo).
- In `hq-src`: `git filter-repo --subdirectory-filter swarm/` → `swarm/` becomes
  repo root with its full commit history (AC-2).
- Secret scan the filtered history (`git log --all` + grep for the real
  `OPENROUTER_API_KEY`/`OPENCODE_API_KEY`/`MAPBOX_TOKEN` values, and the
  `.env`-shaped blob) — **before any push** (spec "Secrets & hygiene").
- The app repo keeps its own history (single remote already `comfort-walking-router`);
  it is not force-pushed. `swarm/` and `specs/harness/` are removed in a normal
  commit during Phase 5.

## Phase 2 — Factory packaging (handleman-hq, local)

- src layout: `src/swarm/` for all core modules.
- `pyproject.toml`: `name = "handleman-hq"`, import stays `swarm`,
  `[project.scripts] hq = "swarm.cli:main"`, build backend `hatchling`,
  `requires-python`/deps carried from `swarm/pyproject.toml`.
- Add `swarm/cli.py` (or `__main__.py`) with `init`, `run`, `up`, `stop`, `dash`,
  `preflight`, `report`, `bench`, `--version`.
- `pip install -e .` in `handleman-hq/.venv`; `hq --version` and `hq preflight`
  work. Unit tests move to `tests/` and pass (774+) under the factory repo.

## Phase 3 — `swarm.yaml` contract in the core

- Introduce `swarm/contract.py`: load `swarm.yaml` from the target repo, with
  defaults that reproduce today's behaviour (so comfort-walking-router is a
  drop-in migration).
- Replace the 5 hardcoded tables (`DEFAULT_SCOPE`, gate defaults, `gates.DEFAULT_MAP`,
  `risk.py` globs, `HARNESS_SPECS`) with contract reads.
- Change `REPO_ROOT` to "the target directory `hq` was invoked in" (CLI passes it;
  `-m swarm.*` keeps a `SWARM_TARGET`/cwd default for back-compat).
- Core-agnostic gate: `grep -rn "app/|frontend/|tests/|contracts/" src/swarm/` empty
  for the *core* (drivers excluded) — AC-4.

## Phase 4 — Driver relocation

- Move `smoke.py`, `e2e.py`, `e2e_guard.py`, `e2e_triage.py`, `db.sh`,
  `acceptance.py` (app parts), `visual.py`, `bench/corpus/` → the app under
  `drivers/`, and `acceptance.mjs`/`playwright` stay in `frontend/`.
- Wire them through `swarm.yaml` (`e2e`, `db`, acceptance/vision commands).
- Assert `grep "from app\|import app" src/swarm/` clean — AC-5.

## Phase 5 — App repo wiring (comfort-walking-router)

- Delete `swarm/` + `specs/harness/` (commit; history preserved).
- Add `swarm.yaml`, gitignore `.swarm/`, the git-tag dependency
  (`swarm @ git+…@v0.2.0`), and a harness venv note in the Makefile.
- Split `Makefile` (app targets + `hq` passthrough), `.env.example` (app keys
  vs `SWARM_*`), `docs/`, `pyproject.toml`.

## Phase 6 — Docs/specs/AGENTS split

- Factory: `README.md` (lead with cheap/model-independent/local-Ollama goals),
  `AGENTS.md`, `GLOSSARY.md`, `LICENSE` (MIT), `docs/` from `swarm/docs/*`,
  `specs/harness/*` from the old repo.
- App: product `docs/*`, `specs/product/*`, its own `AGENTS.md`, `GLOSSARY.md`, `README`.
- `.specify/` templates copied to both.

## Phase 7 — Release + verify

- `gh repo create handleman/handleman-hq --public --license mit`; `git push`.
- Tag `v0.2.0`; `gh release create v0.2.0`.
- App installs `swarm @ git+…@v0.2.0`; `make test` + `make e2e` green; one real
  `hq run` task (040-T13) reaches green.

## Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Filtered history leaks a secret | Phase 1 secret scan before push; `git bundle` backup |
| `REPO_ROOT` rewire breaks a dozen modules | Phase 3 does it once, with a back-compat cwd default + full suite |
| Contract migration drops a gate | Phase 3 defaults reproduce today's behaviour; AC-6 re-runs the real task |
| Force-push the live app repo | Never — app repo only gets a delete commit + `swarm.yaml` |
| `hq` CLI vs existing `swarm` muscle memory | `-m swarm.*` entry points kept; docs cross-reference |

## Rollback

Phases 1–6 are local + commits; revert by deleting the workspace subdirs and
restoring from `/tmp/comfort-full.bundle`. The only non-rollback step is the
public `handleman-hq` push (Phase 7), which is safe by construction (nothing else
depends on it until the app pins the tag).