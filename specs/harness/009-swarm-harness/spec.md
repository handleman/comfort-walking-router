# 009 Swarm Harness — Spec

## What / Why
Local, free-first multi-agent harness to implement existing specs (`001`, `004–008`) with pure CrewAI coder agents + Textual console dashboard. Proves one cheap swarm loop before scaling to full MVP. First swarm target: `001-T1` scaffold only.

Decisions locked with user (2026-10-10): pure CrewAI coders (no OpenCode-as-executor), Textual TUI, Ollama `qwen3.5:9b` / `qwen35-agent:latest` local, free-first routing (local Qwen drafts → OpenRouter `:free` brain roles → Zen free fallback, paid opt-in only).

## Scope
- In scope:
  - `swarm/` Python harness (CrewAI Flows + Crews, `uv` + Python 3.12 venv — system is 3.14.8, CrewAI requires `>=3.10,<3.14`).
  - 3 LLM tiers via `crewai.LLM`: Ollama local (`ollama/qwen3.5:9b`, `http://localhost:11434`), OpenRouter `:free` tool-capable (verified 15 models, e.g. `openrouter/nvidia/nemotron-3-super-120b-a12b:free`, `openrouter/poolside/laguna-s-2.1:free`), Zen OpenAI-compatible free fallback (`muse-spark-1.3-contributor-free`, `space-bunny-free`, etc.).
  - 3 roles for v1: Planner (OpenRouter free), Coder (local Qwen), Reviewer/QA (OpenRouter free, Zen fallback). Sequential `Process.sequential`.
  - Task splitter: parse `specs/*/tasks.md` checkboxes → one CrewAI `Task` per `T-item` with spec/plan context injected; `expected_output` = diff + test evidence.
  - Guarded tools only: `FileReadTool`, `DirectoryReadTool`, custom `EditTool` (exact-match replace), custom `ShellTool` allowlist (`pytest`, `ruff`, `mypy`, `ls`, `git diff --stat` — no network, no `rm -rf /`).
  - Textual console dashboard: per-agent/task panes, live stream via CrewAI event bus (`LLMStreamChunkEvent`), approve/retry keys, cost bar from `crew.usage_metrics`, `run.json` trace per run.
  - Constitution gates enforced by Reviewer + `ShellTool`: `pytest`, `ruff check .`, `mypy .` must pass before task marked done.
- Non-goals:
  - No full `001 T1–T6` swarm run yet (T1 scaffold only as pilot).
  - No web dashboard (FastAPI+Svelte), no CrewAI AMP/Studio hosted UI.
  - No hierarchical manager agent, no auto-merge to `main`, no paid-model default.
  - No `frontend/` swarm coding in v1 (backend/scaffold only; UI tasks stay manual until harness proven).

## Acceptance Criteria
- [ ] AC-1: `swarm/` runs on Python 3.12 venv (`uv venv -p 3.12`, `uv add 'crewai[litellm]' crewai-tools textual`) with `.env` keys (`OPENROUTER_API_KEY`, `OPENCODE_API_KEY`, `OLLAMA_BASE_URL`) never committed; `crewai version` equivalent import works.
- [ ] AC-2: Free-first routing works: Coder calls stay local (Ollama), Planner/Reviewer call OpenRouter `:free` with `tools` support; Zen free reachable as fallback; paid models require explicit `--allow-paid` flag.
- [ ] AC-3: `001-T1` pilot: swarm reads `specs/001-example-app/{spec,plan,tasks}.md` + constitution, produces scaffold diff (`app/`, `frontend/` stubs, `contracts/route.json`, pinned dev deps) with zero manual edits to source files.
- [ ] AC-4: Textual TUI shows live per-agent status, streams chunks, records `swarm/runs/<ts>/run.json` (tasks, tokens, cost, tool calls), supports `a`pprove / `r`etry per task from keyboard.
- [ ] AC-5: Reviewer blocks done unless `pytest` + `ruff check .` + `mypy .` evidence attached; failed gate auto-retries Coder once with error log, then pauses for human.
- [ ] AC-6: Cost of pilot run = $0 (local + `:free` only, verified from `run.json` usage); docs updated (`docs/tech-stack.md` swarm section + `AGENTS.md` swarm commands).
