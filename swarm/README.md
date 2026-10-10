# Swarm harness — usage

Free-first CrewAI swarm that implements `specs/` tasks one at a time (`specs/009-swarm-harness/`).
Pilot scope: `001-T1` only. Roles: Planner + Coder + Reviewer, sequential.

## Prereqs
- `uv` installed; Python 3.12 available (`uv python list`). System Python 3.14 does NOT work with CrewAI (`>=3.10,<3.14`).
- Ollama serving locally: `ollama serve` + `ollama pull qwen3.5:9b` (default `OLLAMA_BASE_URL=http://localhost:11434`).
- Keys (never commit): root `.env` with `OPENROUTER_API_KEY` (planner/reviewer `:free` models), `OPENCODE_API_KEY` (Zen free fallback).

## Setup
```bash
uv venv -p 3.12 swarm/.venv
VIRTUAL_ENV="$PWD/swarm/.venv" uv pip install -p "$PWD/swarm/.venv/bin/python" -e 'swarm/[dev]'
cp swarm/.env.example swarm/.env   # optional overrides; root .env is loaded too
swarm/.venv/bin/python -c "from crewai import LLM,Agent,Task,Crew; print('ok')"
```

## Model tiers (`swarm/llms.py` — the only file that picks models)
| Role | Default | Cost |
| --- | --- | --- |
| Coder | `SWARM_CODER_MODEL=ollama/qwen3.5:9b` (local) | $0 |
| Planner | `SWARM_PLANNER_MODEL=ollama/qwen3.5:9b` (local default; set to a `:free` id for cloud brains) | $0 |
| Reviewer | `SWARM_REVIEWER_MODEL=ollama/qwen3.5:9b` (local default; set to a `:free` id for cloud brains) | $0 |
| Fallback | `SWARM_ZEN_FALLBACK_MODEL=openai/muse-spark-1.3-contributor-free` via Zen | $0 |

> 2026-10-10: OpenRouter `:free` shared pool returns upstream 429s under agentic-loop
> load, so defaults are all-local. Cloud `:free` still works via env override when quota allows.

Paid models are hard-blocked: any non-`:free`/non-local/non-`-free` id raises `PermissionError`
unless `SWARM_ALLOW_PAID=1` in env. Override ids via env, never in code.

Model prefixes route automatically: `ollama/*` → local Ollama, `zen/*` → OpenCode Zen
(`custom_openai` gateway mode), anything else → OpenRouter. Stronger $0 brains, verified 2026-10-10:
- Planner: `SWARM_PLANNER_MODEL=openrouter/nvidia/nemotron-3-super-120b-a12b:free`
- Reviewer: `SWARM_REVIEWER_MODEL=zen/space-bunny-free`
- Coder stays local (`ollama/qwen3.5:9b` + `extra_body={"think": False}`, required for tool calls).

## Run
```bash
make swarm-run                 # pilot 001-T1 headless (or ./swarm/run.sh 001 T1)
make swarm-local               # all-local pilot: Ollama Qwen for every role (overrides cloud .env)
make swarm-dash                 # dashboard attached to the current pilot
make swarm-up                   # pilot in background + dashboard attached
make swarm-up-local             # all-local pilot in background + dashboard attached
make swarm-test                 # harness unit tests (no LLM, no network)
```
Keys: `a`=approve (writes `approved.json`), `r`=retry (new run, same spec/task), `q`=quit.

`--spec` accepts a prefix (`001` → `001-example-app`). Each run writes:
- `swarm/runs/<ts>/run.json` — spec, task, status (`green`/`needs_human`/`crew_error`), gate exit codes, cost (must be `0` for T8).
- `swarm/runs/<ts>/events.jsonl` — streamed agent events; `usage.json` when available.

## Agent tools (guarded, `swarm/tools_guarded.py`)
- `Repo Edit` — exact-match replace, exactly-once occurrence required, repo jail (no path escapes).
- `Guarded Shell` — allowlist only: `pytest`, `ruff`, `mypy`, `git diff`, `ls`, `cat`. 120s timeout, repo cwd. Everything else returns `BLOCKED`.
- Read-only: `FileReadTool`, `DirectoryReadTool`.

## Gates
Reviewer task requires pasted `pytest` + `ruff check .` + `mypy .` transcripts; `flow.gate()` re-runs
all three independently. All green → `green`; else one auto-context retry, then `needs_human` (TUI pauses).

## Unit tests (no LLM, no network)
```bash
swarm/.venv/bin/python -m pytest swarm/tests -v
```

## Traces & logs (all inside the project, never `/tmp`)
- Pilot runs: `swarm/runs/<ts>/{run.json,events.jsonl,usage.json}` (+ `latest` pointer, `approved.json`).
- Ad-hoc probes/debug: `swarm/runs/probes/<name>-<date>.log`. `swarm/runs/` is gitignored.

## Troubleshooting
- `429 free-models-per-min` (OpenRouter): per-minute quota on `:free` (20/min). Wait ~60s and retry; LLMs already set `max_retries=5`. Persistent → change `SWARM_PLANNER_MODEL` to another `:free` id from `curl "https://openrouter.ai/api/v1/models?supported_parameters=tools&sort=pricing-low-to-high"`.
- `Python >=3.10,<3.14 required`: recreate venv with `-p 3.12`.
- Ollama refused: `ollama serve`; check `curl http://localhost:11434/api/tags`.
- `Invalid response from LLM call - None or empty` on local Qwen: thinking blocks break tool parsing — harness already sets `extra_body={"think": False}` on all Ollama LLMs; if you add a new Ollama model id, keep it. Single transient empties still occur; `flow` re-kicks the crew once automatically.
- Local Qwen-9B as **planner** loses the plot (verified 2026-10-10: listed `.git/` internals, asked "what would you like to do" instead of writing the plan). Keep cloud brains (OpenRouter `:free` / Zen) for planner + reviewer; local Qwen is coder-only material with reviewer gates.
- `swarm/.venv/`, `swarm/runs/`, `swarm/.env` are gitignored — safe to run freely.
