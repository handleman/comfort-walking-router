# Changelog

## 2026-10-10 (swarm harness)
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
