# 009 Swarm Harness — Tasks

- [x] T1 (AC-1): Scaffold `swarm/` + Python 3.12 venv + deps (`crewai[litellm]`, `crewai-tools`, `textual`), `.env.example`, `.gitignore` entries; smoke import passes.
- [x] T2 (AC-1, AC-2): Implement `swarm/llms.py` factory (prefix routing: `ollama/*` local, `zen/*` Zen gateway, else OpenRouter; paid guard); per-tier `LLM.call("ping")` verified (nemotron `:free`, `space-bunny-free`, local Qwen).
- [x] T3 (AC-3): Implement `swarm/spec_loader.py` parsing `spec.md`/`plan.md`/`tasks.md` → task objects; unit test on `001` fixtures; `--spec 001 --task T1` filter works.
- [x] T4 (AC-3): Implement guarded tools (`EditTool`, `ShellTool` allowlist + cwd jail) with unit tests (multi-match fail, blocked command fail).
- [x] T5 (AC-2, AC-3, AC-5): Implement `swarm/crew.py` (Planner/Coder/Reviewer, sequential, T-plan/T-code/T-verify) wired to T1 only.
- [x] T6 (AC-4): Implement `swarm/flow.py` + `swarm/events.py` (Flow state, `run.json` + `events.jsonl`, usage/cost capture, `runs/latest` pointer, failure still writes trace).
- [x] T7 (AC-4): Implement `swarm/tui.py` parallel dashboard (per-agent panes, task list, `a`/`r`/`q` keys) + `--tail` attach + `--no-tui` fallback; `swarm/{run,dash,up}.sh` + root `Makefile` (`swarm-run|dash|up|test`).
- [ ] T8 (AC-3, AC-5, AC-6): Pilot run `001-T1` free-only, attach gate evidence, assert `$0` cost, update `docs/tech-stack.md` + `AGENTS.md` + `changelog.md`.
