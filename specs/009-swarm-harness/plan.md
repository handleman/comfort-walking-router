# 009 Swarm Harness — Plan

References `specs/009-swarm-harness/spec.md` AC-1–AC-6. Stack: Python 3.12 venv, CrewAI (Flows + sequential Crew), `crewai.LLM` via LiteLLM, Ollama, OpenRouter, Zen, Textual.

## Approach
Keep harness outside app code (`swarm/` only) so constitution gates for `app/` stay clean. One Flow (`SwarmFlow`) drives one spec-task slice: load spec → split tasks → sequential Planner→Coder→Reviewer crew → gate → log → TUI. No manager agent in v1 (saves tokens, deterministic order). All LLM access through a single `swarm/llms.py` factory so free-first routing is one place to audit.

Verified facts grounding this plan (2026-10-10):
- CrewAI install: `uv tool install crewai`, project dep `uv add 'crewai[litellm]'`; Python requires `>=3.10,<3.14` — system `3.14.8` fails, must pin `3.12`.
- `crewai.LLM` patterns: `LLM(model="ollama/qwen3.5:9b", base_url="http://localhost:11434")`, `LLM(model="openrouter/<id>:free", base_url="https://openrouter.ai/api/v1", api_key=...)`, `LLM(model="openai/<zen-id>", base_url="https://opencode.ai/zen/v1/chat/completions", api_key=...)` with `custom_openai=True` pattern for gateways.
- Local: `ollama list` shows `qwen3.5:9b` + `qwen35-agent:latest` (9.7B, Q4_K_M, 262k ctx, `tools`+`thinking` capable, `num_ctx 65536`).
- OpenRouter `/models?supported_parameters=tools&sort=pricing-low-to-high` returns 368 tool-capable, 15 with `prompt=0` (`:free`), e.g. Nemotron-3 super/ultra, Laguna-S-2.1, Gemma-4, Ling-3.1-Flash.
- Zen free tier exists (`muse-spark-1.3-contributor-free`, `space-bunny-free`, `big-pickle`, etc., all `$0/1M`).

## Steps
1. (AC-1) Scaffold `swarm/` venv + deps.
   - `uv venv -p 3.12 swarm/.venv && uv add --project swarm 'crewai[litellm]' crewai-tools textual python-dotenv`.
   - Files: `swarm/pyproject.toml`, `swarm/.env.example` (`OPENROUTER_API_KEY=`, `OPENCODE_API_KEY=`, `OLLAMA_BASE_URL=http://localhost:11434`, `SWARM_ALLOW_PAID=0`), `swarm/llms.py` (factory: `coder_llm()`, `planner_llm()`, `reviewer_llm()` with paid-guard).
   - Smoke: `swarm/.venv/bin/python -c "from crewai import LLM,Agent,Task,Crew; print('ok')"`.
2. (AC-3 partial) Task splitter `swarm/spec_loader.py`.
   - Parse `specs/<id>/spec.md` (AC list), `plan.md`, `tasks.md` (`- [ ] T<N> (AC-x): ...`).
   - Emit list of `{id, ac_refs, brief, context_paths}`; v1 pilot filters to `001/T1` only via `--spec 001 --task T1`.
   - Unit test with fixture markdown (no LLM needed).
3. (AC-2, AC-3) Crew definition `swarm/crew.py`.
   - Agents: Planner (`role="Spec Planner"`, OpenRouter free, temp 0.2), Coder (`role="Python Scaffold Coder"`, Ollama Qwen, temp 0), Reviewer (`role="QA Gatekeeper"`, OpenRouter free, temp 0).
   - Tools: `FileReadTool`, `DirectoryReadTool`, custom `EditTool(BaseTool)` (args: `path, oldString, newString`, exact-match, fail on multi-match), custom `ShellTool(BaseTool)` (allowlist regex `^(pytest|ruff|mypy|git diff|ls|cat)\b`, timeout 120s, cwd jail to repo root).
   - Tasks: T-plan (expand T1 into file list), T-code (write files via EditTool/shell `mkdir`), T-verify (run gates via ShellTool, attach output). `Process.sequential`, `verbose=False` (TUI handles display via event bus).
4. (AC-4) Flow + tracing `swarm/flow.py`.
   - `class SwarmFlow(Flow[SwarmState])`: `@start load_spec → @listen run_crew → @listen gate → @listen save_run`.
   - `SwarmState`: `spec_id, task_filter, status_per_task, usage, cost, run_dir`.
   - `save_run` writes `swarm/runs/<ts>/run.json` (`{spec, tasks, agent→model, tool_calls, usage_metrics, gate_results}`) + `events.jsonl`.
   - Event listener (`swarm/events.py: SwarmListener(BaseEventListener)`) forwards `LLMStreamChunkEvent`/task events to TUI queue + `events.jsonl`.
5. (AC-4) Textual TUI `swarm/tui.py`.
   - Layout: header (spec/run/cost), left pane task list, right pane selected agent log stream, footer keys (`a` approve, `r` retry, `q` quit, `p` toggle paid-guard).
   - Runs Flow in worker thread; TUI polls queue. Retry re-kicks `crew.kickoff()` for failed task only with prior error in inputs.
   - Fallback `--no-tui` mode: Rich live log + same `run.json` (for CI/headless).
6. (AC-5) Gate enforcement.
   - Reviewer task `expected_output` template requires `pytest ... / ruff ... / mypy ...` transcripts; `flow.gate()` re-runs `ShellTool` independently (don't trust agent claim). Fail → one auto-retry with log tail; second fail → `status=needs_human`, TUI pauses.
7. (AC-3, AC-6) Pilot `001-T1` + docs.
   - `swarm/.venv/bin/python -m swarm.flow --spec 001 --task T1 --no-paid` → expect scaffold diff only.
   - Human reviews diff, runs gates manually once, then updates `docs/tech-stack.md` (swarm section) + `AGENTS.md` (swarm venv, run single task, TUI commands). Pilot cost assertion: `jq .cost swarm/runs/<ts>/run.json == 0`.
8. Cleanup: `.gitignore` (`swarm/.venv/`, `swarm/runs/`, `swarm/.env`), `changelog.md` entry.

## Risks / Open Questions
- Python pin: system 3.14 unsupported by CrewAI — mitigated by `uv venv -p 3.12`; CI must use same pin (ADR-010 follow-up).
- Qwen-9B tool-call quality: local coder may mangle `EditTool` args → mitigation: strict Pydantic `args_schema`, low temp, Planner pre-expands exact file ops, Reviewer retries once then human.
- OpenRouter `:free` rate limits / rotation: 15 models today, list churns → `llms.py` holds ordered fallback list (`laguna-s-2.1:free` → `nemotron-3-super:free` → `ling-3.1-flash`), configurable via env.
- Zen endpoint shape: docs show per-model endpoints (`/chat/completions` vs `/responses` vs `/messages`); v1 uses only `/chat/completions`-compatible free chat models via OpenAI-compat `LLM` — verify with one curl before wiring Reviewer fallback.
- Textual scope creep: cap v1 at status/stream/approve/retry/cost; defer web dashboard, parallel multi-task crews, auto-PR to later specs.
