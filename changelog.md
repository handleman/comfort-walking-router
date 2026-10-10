# Changelog

## 2026-10-10 (swarm harness)
- swarm: agent rules from T2 findings (`FIX_RULES` shared by fix + senior crews: resolvable imports, sync/async match, ABC signatures, `ruff check --fix` first, delete strays); `MAX_FIX_ROUNDS` 1→2, senior retries ×2 (`SENIOR_ATTEMPTS`); role-sequence mermaid diagram in `swarm/README.md`
- swarm: cross-spec loop — green runs advance planner→dev→QA across specs in directory order (specs without `tasks.md` and `009-swarm-harness` skipped); TUI rebuilds task list per spec/task in live + tail modes
- swarm: senior escalation — dev phase retries ×3 (`DEV_ATTEMPTS`), then one senior pass (`SWARM_SENIOR_MODEL=openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`, tool-calling verified, must differ from planner) + QA re-verify; Zen free tier unusable from harness (FreeTierError), OpenRouter Claude all priced
- swarm: autonomous loop — green runs autocommit in-scope scaffold + push (`swarm: <spec>-<task> green (autocommit)`, `.env*` refused), then loop back to planner for next task (`run_tasks`, `--single`/`--no-commit` escapes); TUI tail mode shows plan-cached note via run `meta.json` (was live-mode only)
- swarm: pilot 001-T1 end-to-end at $0 — 6 micro-steps + reviewer PASS (pytest/ruff/mypy exit 0); `needs_human` only on the scope gate flagging the human's own uncommitted `llms.py` fix (committed same day, scope clean after)
- fix: gates green at root — `pytest`/`ruff`/`mypy` resolve via `swarm/.venv` PATH in `ShellTool`, packaging (`swarm/__init__.py`, `tests/__init__.py`), root ruff per-file-ignores for deliberate broad-excepts; installs: ruff/mypy/fastapi in swarm venv; scope guard (`DEFAULT_SCOPE` + `scope` gate, pilot confined to scaffold paths)
- fix: coder empty-response root cause — CrewAI routed `ollama/*` via its native openai_compatible client, silently dropping `extra_body`, so `think:false` never reached Ollama and Qwen thinking broke tool calls; `coder_llm` + local override now force `is_litellm=True` (+ regression `test_llms_routing.py`); step-5 repro passes end-to-end
- swarm: implement 009 T1–T7 — `swarm/` (CrewAI 1.15.27, Python 3.12 venv), prefix-routed free-first LLMs, guarded tools, Flow + event trace, parallel Textual dashboard with `--tail` attach, `run/dash/up.sh` + root `Makefile`
- swarm: findings — OpenRouter `:free` 429s under loop load; Qwen thinking breaks LiteLLM tool parsing (`extra_body={"think": False}`); Zen needs `custom_openai` gateway + v1-root base; verified brains (nemotron `:free`, `space-bunny-free`, local Qwen)
- docs: README entry + quickstart (`make swarm-*`), tech-stack swarm section, AGENTS commands, 009 tasks T1–T7 checked; T8 pilot in progress

## 2026-10-04
- docs: add changelog skill and bootstrap changelog.md
- chore: changelog skill (`.opencode/skills/changelog/`)
- docs: update plans for Comfort-First Walk and add ADRs for Live-Position Structure, Testing Strategy, and Dev-CI Environment
- docs: add specifications and plans for Weather-Sun, Saved Routes, and Comfort-Plus features
- docs: update tech stack, roadmap, and specifications for Mapbox integration and comfort features
- docs: update tech stack details to include TypeScript and npm run check
- Merge branch 'main' of github.com:handleman/comfort-walking-router
- docs: mission, stack (FastAPI+Svelte+Leaflet), roadmap, 001 spec-plan-tasks
- Initial commit
- chore: scaffold Spec-Kit SDD layout with constitution, templates, and blank docs
