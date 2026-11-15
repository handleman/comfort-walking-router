# Setup and models

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Prereqs
- `uv` installed; Python 3.12 available (`uv python list`). System Python 3.14 does NOT work with CrewAI (`>=3.10,<3.14`).
- Ollama serving locally: `ollama serve` + `ollama pull qwen3.5:9b` (default `OLLAMA_BASE_URL=http://localhost:11434`).
- Keys (never commit): root `.env` with `OPENROUTER_API_KEY` (planner/senior `:free` models);
  `OPENCODE_API_KEY` only if you route a role to `zen/*` (Zen's free tier is client-only, so the
  API path is paid — see the model table).

## Setup
```bash
uv venv -p 3.12 swarm/.venv
VIRTUAL_ENV="$PWD/swarm/.venv" uv pip install -p "$PWD/swarm/.venv/bin/python" -e 'swarm/[dev]'
cp .env.example .env   # optional overrides (keys stay empty until you fill them)
swarm/.venv/bin/python -c "from crewai import LLM,Agent,Task,Crew; print('ok')"
```

## Project-agnostic core
The harness does not hardcode a language or framework. Gate commands come from
`SWARM_GATE_COMMANDS` (semicolon/newline separated), scope from `SWARM_SCOPE`, and
the coder prompt is stack-inferred. Point those at another project and the same
flow works; only the guard *implementation* (`swarm/tools_guarded.py` path/secret
rules) is repo-specific.

## Model tiers (`swarm/llms.py` — the only file that picks models)

Current operator profile (**OpenCode Go**, 2026-11-15): local Ollama is off
(`SWARM_LOCAL_FIRST=0`), one subscription key serves every role, and each role
falls back to a second Go model.

| Role | Model | Cost (Go) |
| --- | --- | --- |
| Planner | `opencode-go/glm-5.3-flash` (fallback `opencode-go/qwen3.8-flash`) | $0.15/$0.50 per M |
| Coder | `opencode-go/glm-5.3-flash` (fallback `opencode-go/qwen3.8-flash`) | $0.15/$0.50 per M |
| Reviewer / QA | `opencode-go/glm-5.3-flash` (fallback `opencode-go/qwen3.8-flash`) | $0.15/$0.50 per M |
| Verifier | `opencode-go/glm-5.3-flash` (fallback `opencode-go/qwen3.8-flash`) | $0.15/$0.50 per M |
| Senior / verdict fallback | `opencode-go/glm-5.3-flash` (fallback `opencode-go/qwen3.8-flash`) | $0.15/$0.50 per M |

`opencode-go/*` is its own routing prefix: `OPENCODE_GO_API_KEY` (or
`OPENCODE_API_KEY`) against `SWARM_GO_BASE_URL`
(default `https://opencode.ai/inference/go/openai/v1`), with the client
`User-Agent` and an `x-opencode-session` header that the Go gateway asks for
(it drives routing and prompt caching). Model ids are the bare console ids
(`glm-5.3-flash`, `qwen3.8-flash`, `deepseek-v4.1-flash`, `kimi-k2.7-code`, …);
prices live in `swarm/usage.py`, so `run.json.cost` stays a number.

Two Go caveats seen on 2026-11-15: `deepseek-v4.1-flash` is region-blocked until
the workspace privacy setting is **Global** (Settings › Privacy › Regions), and
its price is peak/off-peak — the table stores the peak rate so the per-task cap
never under-reads.

Measured on 2026-11-15 with `make swarm-bench-live CASE=004-weather-sun-T2`:
**green in 111 s / 131 s, $0.0075 / $0.0074, 0 fix rounds**, versus 384 s /
$0.0161 on the same case with the Zen profile. One case, not a benchmark.

The earlier cloud-only profile (2026-11-14) was DeepSeek on OpenRouter for the
planner and `zen/glm-5.3-flash` for the four tool roles; it still works if the
Go subscription is absent.

The free Nvidia roles worked all day until OpenRouter's **1000 free requests/day**
limit hit (`429 free-models-per-day-high-balance`). With no free fallback left,
the operator pointed reviewer/verifier/senior at the paid Zen model instead of
waiting for the reset; `SWARM_ALLOW_PAID=1` now also covers those roles (an
explicit `allow_paid` argument still wins). With a healthy free tier, set them
back to `:free` ids — the code defaults are free-only.

Offline variant (no keys, slowest): `make swarm-local` sets every role to Ollama —
coder `swarm-coder`, reviewer `swarm-qa` (Qwen3.5 9B, 262k ctx). The 2026-11-08
free-first defaults were planner `nemotron-3.5-super-vl:free`, local coder/QA and
the free ultra senior. The free Nvidia planner returned 503 "content safety
screening is temporarily unavailable" for ~7 minutes (2026-11-14, 014-T6), which
is why the planner is now paid DeepSeek.

On a quota/429 the flow switches that role to `SWARM_<ROLE>_FALLBACK_MODEL`
(default `SWARM_LOCAL_FALLBACK_MODEL`, still `ollama/swarm-coder:latest` in code;
the operator `.env` points it at `zen/glm-5.3-flash` because local is off), then retries.

Free/cheap menu (re-checked live with a tool-call probe; ids churn, so run
`make swarm-preflight` before trusting them):
- OpenRouter `:free` tool-capable: `nvidia/nemotron-3.5-super-vl:free`,
  `nvidia/nemotron-3-ultra-550b-a55b:free`, `recursive/flint-v1.0:free`,
  `cohere/north-mini-code:free`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`.
  (`google/gemma-4-*:free` was upstream-429; `nvidia/nemotron-3.5-lightning:free` did not
  emit tool calls. The old planner id `nemotron-3-super-120b-a12b:free` is gone.)
- Ollama local: `swarm-coder`/`swarm-qa` (Qwen3.5 9B, 262k ctx), `qwen3.5:9b`,
  `qwen35-agent`, `llama3.2:1b` (tools work but emits malformed args — not a coder).
- Zen: **free models are client-only** (`FreeUsageLimitError` when called with an API key);
  paid models work from the API — `deepseek-v4.1-flash` (~$0.00002/call) and
  `glm-5.3-flash` are the cheapest. `gpt-5.4-nano` and `beam-free` are region-blocked (DE).

Paid models are hard-blocked: any non-`:free`/non-local/non-`-free` id raises `PermissionError`
unless `SWARM_ALLOW_PAID=1` in env. Override ids via env, never in code.

Model prefixes route automatically: `ollama/*` → local Ollama, `zen/*` → OpenCode Zen
(`custom_openai` gateway; `SWARM_ZEN_BASE_URL` must stop at `/v1` — the SDK appends
`/chat/completions`, a full URL gives 404).

## Local Postgres (005 saved routes)

```bash
make swarm-db-up       # colima + comfort-pg, wait, migrate, print the export
make swarm-db-status
make swarm-db-down     # COLIMA=1 also stops colima
```

While the container runs, `make test`, `make e2e`, `make swarm-run`, `make swarm-up`,
`make swarm-bench-live` and `make swarm-replay*` get `DATABASE_URL` automatically
(`$(DB_ENV)` in the Makefile) — the app reads the environment at import, not
`.env`. Without it, the 005 repository tests and the three `preferences` e2e
specs skip. `make swarm-preflight` prints the database line but never fails on it.

## Preflight (before the first LLM call)
```bash
make swarm-preflight                              # roles/models, keys, Ollama pull, cloud lists, venvs, gates
swarm/.venv/bin/python -m swarm.preflight --offline   # skip provider model-list requests
```
`run_crew` runs the same checks automatically and stops with `preflight_failed` if any fail
(`SWARM_SKIP_PREFLIGHT=1` bypasses). This is 012 T12.

Coder image: `swarm/ollama/Modelfile` (`FROM qwen3.5:9b`, temp 0, `num_ctx 65536`,
baked SYSTEM discipline). Use it via `SWARM_CODER_MODEL=ollama/swarm-coder:latest`.
Verified 2026-10-10: builds offline from local blobs, native tool calls work
(with the harness's `think:false`). Tune `num_ctx`/SYSTEM in the Modelfile and rebuild.
