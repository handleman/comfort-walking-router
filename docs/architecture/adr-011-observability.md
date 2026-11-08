# ADR-011: Swarm Observability — Local Operator Dashboard + Optional OTel Traces

## Context
Phase 0/1 of 012 added the data an operator needs: `run.json` now records status,
gates, reviewer verdict, run delta, approval, commit/push, and a `usage` block
(tokens, models, cost, start/finish/duration), while `events.jsonl` carries the
live agent stream. The existing Textual UI only showed three log panes and a
one-line status with a hardcoded `cost=$0`, so most of that evidence was invisible.

Before building more UI we surveyed existing solutions for dark-factory / agent-swarm
observability (2026-11-08):

- **LLM tracing platforms** — Arize Phoenix, Langfuse, AgentOps, PandaProbe.
  All instrument CrewAI through OpenInference/OpenTelemetry (`openinference-instrumentation-crewai`)
  and give per-call spans, token/cost rollups, evals, and replay. Phoenix runs fully
  local with one process; Langfuse self-hosting needs Postgres + Redis + ClickHouse + S3;
  AgentOps is CrewAI-native but SaaS-first.
- **Factory / agent control planes** — Myrmecia, AgentFactory, SwarmWeaver,
  `frontier-loom-ui`, `herdr-dagr`, Factory's web UI. They model queues, workers,
  attempts, gates, evidence tiers, approvals, and cost, but each owns a new state
  store/API and expects to be the orchestrator. `herdr-dagr` is the closest prior art:
  a read-only pane that renders a producer-owned `run.json` (tasks, attempts, gates,
  evidence tiers) and never writes state.
- **Dark-factory guidance** — the useful patterns are risk classes, station-level
  gates with owners, provenance at merge, a drilled halt path, and evidence tiers
  ("verified" vs "agent said done"), not a specific dashboard product.

## Decision
- Keep the **Textual dashboard as a read-only view** over `run.json` / `events.jsonl`
  (`swarm/tui.py`). It owns no state and adds no dependencies. It shows:
  queue + newest per-task outcome, models (with local/fallback markers), per-run
  tokens/cost/time against budgets, gates/exit codes, recent runs, approval state,
  and live agent panes. It opens **fresh** (skip events logged before attach; clear
  panes per task) and exposes history on demand (`h` toggle, `p`/`n` run browsing),
  so long autonomous runs do not flood a new session. Keys: `a` (approve), `r` (retry),
  `h` (history), `p`/`n` (older/newer run), `t` (latest), `q` (quit).
- **Do not adopt a second control plane** (Myrmecia/SwarmWeaver/AgentFactory): the
  harness already owns queue, lock, approval, gates, and commit; duplicating them
  would create two sources of truth for a single-worktree factory.
- **Per-call tracing is optional and additive**: if deeper debugging is needed,
  install `openinference-instrumentation-crewai` and point OTLP at a local Phoenix
  (`python -m phoenix.server.main serve`). Nothing in `run.json` depends on it.
- Keep the event bus and `usage` fields as the contract for any future renderer
  (web or external collector).

## Alternatives Considered
- **Adopt Phoenix/Langfuse as the dashboard**: strong span UX, but they do not know
  specs, ACs, gates, approvals, or the merge queue, and Langfuse self-hosting is a
  four-service stack. Better as an optional trace sink.
- **Adopt an agent control plane**: duplicates run state and would replace the
  harness's safety model (lock, run delta, truthful green).
- **Build a web dashboard**: a React/WebSocket app is a larger surface than the
  current need; the TUI already runs where the pilot runs and works over SSH.
- **Prometheus/Grafana**: good for metrics over time, but poor for per-run evidence
  and queue/gate drill-down without a second exporter.

## Consequences
- One source of truth: `run.json`/`events.jsonl` remain the contract; the TUI and any
  future exporter are disposable views.
- The dashboard runs offline and free; no API keys or containers.
- Deep span search/evals are not available in the TUI. When needed, add the
  OpenInference exporter behind `SWARM_OTEL_*` env vars (tracked as a follow-up, not
  a Phase 1 requirement).
- The queue pane reads run history on a timer; a very large `swarm/runs/` will need
  retention/pruning (runs are gitignored, so pruning is safe).
