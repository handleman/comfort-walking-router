# 009 Swarm Harness — Tasks

- [ ] T1 (AC-1): Scaffold `swarm/` + Python 3.12 venv + deps (`crewai[litellm]`, `crewai-tools`, `textual`), `.env.example`, `.gitignore` entries; smoke import passes.
- [ ] T2 (AC-1, AC-2): Implement `swarm/llms.py` factory (coder=Ollama Qwen, planner/reviewer=OpenRouter `:free`, Zen free fallback, `--allow-paid` guard); verify each tier with one tiny `LLM.call("ping")`.
- [ ] T3 (AC-3): Implement `swarm/spec_loader.py` parsing `spec.md`/`plan.md`/`tasks.md` → task objects; unit test on `001` fixtures; `--spec 001 --task T1` filter works.
- [ ] T4 (AC-3): Implement guarded tools (`EditTool`, `ShellTool` allowlist + cwd jail) with unit tests (multi-match fail, blocked command fail).
- [ ] T5 (AC-2, AC-3, AC-5): Implement `swarm/crew.py` (Planner/Coder/Reviewer, sequential, T-plan/T-code/T-verify) wired to T1 only.
- [ ] T6 (AC-4): Implement `swarm/flow.py` + `swarm/events.py` (Flow state, `run.json` + `events.jsonl`, usage/cost capture).
- [ ] T7 (AC-4): Implement `swarm/tui.py` Textual dashboard (task pane, log stream, `a`/`r`/`q`/`p` keys) + `--no-tui` Rich fallback.
- [ ] T8 (AC-3, AC-5, AC-6): Pilot run `001-T1` free-only, attach gate evidence, assert `$0` cost, update `docs/tech-stack.md` + `AGENTS.md` + `changelog.md`.
