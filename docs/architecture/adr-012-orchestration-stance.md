# ADR-012: Orchestration Stance — CrewAI Flow Now, Durable Event-Sourced Orchestrator as an Option

## Context

The swarm is a custom control plane: `swarm/flow.py` sequences planner → coder →
017 self-check → 019 verifier → QA → fix rounds → commit/merge, with CrewAI
crews as the workers. Recovery today is *recording*, not durable execution:

- `events.jsonl` — append-only, but telemetry: the TUI tails it, nothing derives
  state from it (`swarm/events.py`).
- `run.json` — terminal/updating summary; the operator's and the dashboard's view.
- `progress.json` — a per-micro-step checkpoint (plan hash, step list, completed
  index, per-step output tails, run-delta hashes, age). A plan/steps/spec
  mismatch restarts the task; a delta-hash drift redoes only the last step
  (`013` AC-7–AC-9, `015` AC-7).
- Done ledger — git trailers (`Swarm-Task`/`Task-Hash`/`Spec-Hash`), survives
  `swarm/runs/` deletion and process restarts (`013`).
- `shell_log.jsonl` — gate executions; the only source of green (`015`).
- Single-run lock + worktrees + merge queue — one pilot, one task at a time.

That is crash recovery at task and step boundaries. It is **not** the durable
execution contract the market converged on in 2026: one authoritative event
history, deterministic replay, resumable nodes, idempotent side effects, and
leases that allow concurrent workers. The 2026-11 investigation
(`docs/research/dark-factory-market-2026.md`) measured the cost of *not* having
it (31 non-green stops in 86 runs) but also showed that our measured bottleneck
is efficiency (59% fix rounds, 4.8M QA prompt tokens), not orchestration.

On 2026-11-12 the operator decided: efficiency first (`specs/020-*`), then
parallelism (`021`), then earned autonomy (`022`), and **stay on the CrewAI Flow
with a durable event-sourced orchestrator recorded as a future option**. This
ADR writes that option down so "future option" means a design with triggers and
seams, not folklore.

Vocabulary used here:

- **Crash recovery** — restart a run and continue from a snapshot (today).
- **Durable execution** — an append-only journal is the authority; the process
  can be killed at any instruction, replayed, and resumes at the same node
  without repeating completed work or duplicating side effects.

## Decision

1. **Crews stay the worker layer.** `swarm/crew.py` role agents and tools remain
   how a micro-step executes. No framework migration in 020–022.
2. **`swarm/flow.py` stays the control plane.** We keep hardening it; we do not
   claim durable execution. Docs and run records say "crash recovery" for what
   `progress.json` does.
3. **The durable orchestrator is a recorded option with a defined shape**, not a
   deliverable: an in-repo event-sourced kernel (journal + step queue + leases +
   effect keys) with CrewAI crews as *activities*. External engines are a
   fallback for triggers this repo is not expected to hit (multi-host, long
   missions), not the default.
4. **Keep the option cheap now** with four seams that are ordinary hardening
   work, not a rewrite:
   - **One write path.** Every state transition emits an event
     `{run_id, step, attempt, key, type, payload, at}`; `run.json` becomes a
     derived view, not a second authority. `events.jsonl` is already the seed.
   - **Effect keys.** Commit, merge, push, approval and gate runs carry an
     idempotency key so a retry is a no-op (merges are already ref-checked;
     commits should be keyed by `(run_id, step, delta_hash)`).
   - **Step contract.** Step inputs/outputs are serializable and steps hold no
     module-level state, so a step can be replayed from a journal row.
   - **Quarantine recovery.** Checkpoint validation, stash restore and
     resume-point derivation live behind one module, so swapping the kernel
     touches one file instead of fifteen call sites in `flow.py`.
5. **The trust surface does not change.** Green is still QA-only gate evidence
   (`015`); the verifier (`019`) and self-check (`017`) still cannot make a run
   green. Durability changes *how work is resumed*, never *what counts as done*.

## Event-driven options considered

All of these implement the same idea — record completed work, replay on failure —
with different ownership of the journal. The relevant question for this repo is
not "which engine is best" but **"where does the journal live, and does the
harness keep owning queue, gates, evidence and merge?"**

| Option | Mechanism | Journal | Ops footprint | Keeps CrewAI + our flow | Verdict |
| --- | --- | --- | --- | --- | --- |
| **A. Harden in place** (today) | Snapshots (`progress.json`), done ledger, effect keys, richer events | Files + git | None | Yes, unchanged | **Now.** Minimum work, most practical recovery value |
| **B. CrewAI Flow-native** | Real `Flow` with `@start/@listen/@router`; `@persist` (`SQLiteFlowPersistence`) snapshots flow state per method; `@human_feedback` + `from_pending().resume()`; `kickoff(inputs={"id": ...})` resumes lineage; `restore_from_state_id` forks | CrewAI SQLite | None | Crews yes; control flow must be restructured into flow methods | **Cheapest future step.** Good for approval holds; not a recovery authority (persists `state`, not git; per-method, not per-tool-call) |
| **C. In-repo kernel** (recorded default) | SQLite/Postgres tables `events`, `steps`, `attempts`, `leases`, `effects`; dispatcher claims steps, crews are activities, results are journaled | Ours | None (SQLite) → Postgres when concurrent | Yes: queue, gates, evidence, merge stay ours | **Promote on trigger.** Same shape as a Temporal workflow with 200 lines of engine |
| **D. DBOS Transact** | Library in the process; `@DBOS.workflow`/`@DBOS.step`; checkpoints in Postgres; durable queues with `deduplication_id`; recovery re-enqueues PENDING workflows by executor id | Postgres | Postgres only (already in the stack for 005) | Crew calls become steps; queue still configurable | **Best external fit** if we accept a Postgres dependency for the harness |
| **E. Restate** | Single Rust binary, replicated log + RocksDB; handlers are HTTP services; `ctx.run()` journals side effects; durable promises/signals; `idempotency-key` on ingress | Restate server | One binary + persistent volume | Crews become handlers behind HTTP; flow shape changes | **Second external fit.** Local-friendly, but BSL server and push-model impedance |
| **F. Temporal** | Deterministic workflows; all I/O in activities; event-history replay; durable timers; retry policies; replay tests detect non-determinism | Server + DB | Multi-service cluster + Cassandra/MySQL/Postgres (SQLite dev only) | Crew calls become activities; workflow logic must be deterministic | **Deferred.** Most mature, most ops; versioning/running-workflow constraints fight a weekly-changing harness |
| **G. Hatchet** | Postgres-backed queue + DAG + durable tasks (deterministic variant of Temporal); workers over gRPC; Lite single image | Postgres | Engine/API + Postgres (RabbitMQ optional) | Tasks yes; durable tasks import determinism rules | **Deferred.** MIT and pragmatic, but a separate control plane we would have to keep in sync with ours |
| **H. Inngest** | Event-triggered durable functions; `step.run` memoized by hashed step id; durable sleep/wait-for-event; self-hosted server calls your HTTP handlers | Server + Postgres/Redis | Server binary + PG/Redis (SQLite dev) | HTTP-handler shape; server SSPL | **Rejected for now.** Event triggers are attractive; license and handler shape are not |
| **I. LangGraph** | Graph runtime with checkpointers; durability modes `sync`/`async`/`exit`; `interrupt()`; time travel via `get_state_history` | Postgres/SQLite saver | None beyond DB | Would *replace* the flow; replay re-executes LLM nodes, so results differ | **Rejected.** A rewrite that does not address the measured bottleneck |

Two design facts that decide most of the table:

- **The state that matters is git, not the flow's pydantic model.** A resume is
  only trustworthy if the worktree, delta hashes and done ledger agree. Any
  engine must externalize commit/merge/push as idempotent activities and keep
  our `015` evidence rule; the engine cannot own green.
- **A crew call is a long, non-deterministic activity.** It must be recorded and
  replayed as a result (activity/step), never re-derived by deterministic
  workflow code. Engines with a determinism contract (Temporal, Hatchet durable
  tasks, Restate's context-call sequence) force this split; so does option C.

### Option C shape (the recorded future default)

```
events(seq INTEGER PRIMARY KEY, run_id, at, type, step, attempt, key, payload)
  UNIQUE(run_id, key)                  -- idempotent emission
steps(run_id, idx, status, attempt, lease_owner, lease_until, output_digest)
effects(key PRIMARY KEY, run_id, kind, result, at)   -- commit/merge/push/approval
```

Rules: events are append-only; state is a fold over them (materialized into
`run.json`/TUI views); a step is claimed with one atomic
`UPDATE … WHERE status='queued' OR lease_until < now`; a heartbeat extends the
lease; every external effect checks `effects` first. SQLite in WAL mode with a
single writer is enough for the pilot; Postgres when `021` runs real workers.

What "done" looks like for a kernel promotion: a `kill -9` at each phase
(planning, crew call, gate, commit, merge) resumes without repeating completed
steps or duplicating a commit/merge, and folding the journal reproduces the
`run.json` the operator saw. That is a testable contract, unlike "the checkpoint
looked valid".

## Alternatives considered (rejected now)

- **Migrate to LangGraph or Microsoft Agent Framework now.** Both replace the
  orchestration we already own, add a new API surface, and leave the measured
  waste (fix rounds, prompt tokens, gate cost) untouched. Revisit only if graph
  control flow itself becomes the constraint.
- **Adopt Temporal now.** The most mature engine, but a multi-service cluster
  plus database, and a determinism contract that every harness change must
  respect (replay compatibility, worker versioning). Disproportionate for one
  pilot process.
- **Move the harness into DBOS today.** The lightest external option and the
  best fit if we ever want one, but it adds a Postgres requirement to runs that
  are currently offline/free-local, and DBOS 3.0's schema break shows the
  library is still moving. Keep it as the first external candidate.
- **Add a broker/queue (Redis, RabbitMQ, Kafka).** Durability does not come from
  a broker; it comes from a journal plus idempotent effects. This adds a service
  and keeps the hard part.
- **Build a second control plane / buy a dark-factory product.** Already
  rejected in ADR-011: it would duplicate queue, evidence and merge state.
- **Use `@persist` as the recovery authority now.** It persists flow state, not
  the worktree/delta/ledger; a resume could disagree with git. Useful later for
  out-of-process approval (`@human_feedback` + `from_pending().resume()`), which
  is currently `make swarm-approve`.

## Consequences

- No rewrite risk in 020–022; every hour goes to the measured waste first.
- Recovery stays approximate until a trigger fires: a crash mid-crew re-runs that
  step, and safety depends on effect keys rather than an engine. This is
  acceptable because steps are bounded and merges are ref-checked.
- Concurrency stays capped by the single-run lock. `021` will either fit inside
  that (parallel *steps* in one task, sequential tasks) or trip the first
  trigger and promote option C.
- Approvals stay in-process (`make swarm-approve`, TUI `a`). Out-of-process
  approval is a small future use of CrewAI's `@human_feedback`.
- The ADR fixes the vocabulary: "durable execution" is not claimed anywhere
  until the journal is authoritative and replay is tested.

## Triggers to promote the option

Measurable, not aesthetic — any one is enough:

1. `021` needs more than one worker on the repo (leases/queue required).
2. A crash mid-crew or mid-merge costs a re-run materially above p50 (see
   `run.json.recovery`, `events.jsonl` deltas), or a duplicate side effect is
   observed despite effect keys.
3. A contested green ("green but wrong", the 014-T2 class) needs replay rather
   than log reading more than occasionally.
4. Resume on another machine, or runs long enough (hours / multi-day missions)
   that a process-bound lock is the limit.
5. More than ~2 re-executions of the same step per task become normal.

When a trigger fires, promote **option C**; if it fires for multi-host or
sustained >1h workflows, evaluate **DBOS** first and **Restate** second. Keep
crews and the green contract in every case.

## References

- `docs/research/dark-factory-market-2026.md` (market survey, baseline, decisions)
- `specs/020-harness-efficiency/spec.md` (efficiency phase, decision record)
- `specs/013-dark-factory-phase-2/` (done ledger, checkpoints), `specs/015-dark-factory-economics/` (evidence, recovery), `specs/019-scenario-verifier/`
- ADR-011 (observability: the TUI is a view over `run.json`/`events.jsonl`)
- CrewAI Flows: persistence (`@persist`, `from_pending`/`resume`, `@human_feedback`), docs.crewai.com
- Temporal: determinism/replay, activity idempotency keys, self-hosted persistence
- Restate: journal/replay, `ctx.run`, durable promises, single-binary server (BSL 1.1)
- DBOS Transact: `@DBOS.workflow`/`@DBOS.step`, Postgres checkpoints, durable queues/dedup
- Hatchet: Postgres-backed tasks/durable tasks, Lite image; Inngest: step memoization, self-hosting
- LangGraph: checkpointers, durability modes, time travel (`get_state_history`)
