# Dark-factory market survey and harness gap analysis (2026-11)

Status: investigation. Feeds `specs/020-*`. Sources are dated in the text; vendor
claims are labelled as claims, not benchmarks.

## Why this exists

Our harness already runs a real dark-factory loop: spec → plan → tasks → coder
crews → QA gates → commit/merge, unattended, free-first. It is also a custom
control plane with 8.8k lines of Python, one task at a time, and a 63% green
rate. The question is not "should we copy a vendor". It is: **which proven
patterns would buy the most efficiency, autonomy and speed for the least new
trust surface?**

This document:

1. maps the market into the four layers that matter (durable orchestration,
   control planes, spec-driven tooling, verification/evaluation),
2. compares our harness against representative implementations on the axes we
   care about,
3. measures our own baseline from `swarm/runs/`,
4. lists growth opportunities with impact, effort and risk,
5. proposes a phased program, leaving the scope decision to the spec.

## The market in four layers

Most "dark factory" products are assembled from the same four layers. Comparing
a product to our harness only makes sense layer by layer.

### 1. Durable orchestration frameworks

| Project | Model | What it gives you | What it does not |
| --- | --- | --- | --- |
| **LangGraph** (LangChain, MIT) | Explicit graph: typed state, nodes, edges, conditional cycles | Checkpointers (Postgres in production), `interrupt()` for human approval, replay, supervisor/swarm patterns | It is a low-level library: you own the graph, the prompts, the tool gateway and the audit log |
| **CrewAI** (MIT) — ours | Crews (role agents) inside Flows (event-driven steps) | `@start`/`@listen`/`@router`, typed flow state, `@persist` (SQLite by default), `@human_feedback` | Fewer durable-execution guarantees than LangGraph; we own idempotency and recovery |
| **Microsoft Agent Framework 1.0** (MIT) | AutoGen's successor: agents + graph workflows | Sequential/concurrent/handoff/group-chat/Magentic patterns, checkpointing, approvals, .NET + Python | Azure/Microsoft gravity; new API surface |
| **OpenAI Agents SDK** | Agents + handoffs + guardrails + sessions + tracing | Simple agent loop, tool guardrails, built-in tracing | Not a scheduler or a queue; production durability is yours |
| **Google ADK** | Agent Development Kit, Gemini-centric | Multi-agent composition, tools, evaluation | Google-cloud gravity |

Relevant market fact: **AutoGen is archived** (maintenance mode since
2025-10-02), and Microsoft points new work at Agent Framework. The practical
2026 comparison is LangGraph vs CrewAI vs Agent Framework, not AutoGen.
([HoneyHive, 2026-11-06](https://www.honeyhive.ai/learn/langgraph-vs-crewai-vs-autogen);
[Vision Nexera, 2026-11-02](https://www.visionnexera.com/insights/langgraph-vs-crewai-vs-autogen-for-enterprise-multi-agent-systems))

**Read for us:** our Flow is closer to a hand-written LangGraph: deterministic
listeners around CrewAI crews. We already have most of the *control*; we lack
the *durability contract* (one event log, resumable at any node, idempotent
side effects) that LangGraph/OpenHands make first-class.

### 2. Autonomous control planes ("dark factory" products)

| Product | Isolation / execution | Coordination | Verification | Autonomy envelope |
| --- | --- | --- | --- | --- |
| **Factory (Droids 1.0, 2026-10-29)** | Local, cloud, on-prem, air-gapped; Droid Computers for long runs | Droids, Automations, **Missions** (multi-day, parallel tracks) | Code review, browser-driven QA, STRIDE/OWASP, risk tiers, policy hooks | Model router, signal→production, "autonomy ratio" metric, humans own rules |
| **Cognition Devin** | Cloud VM per session, MultiDevin; Outposts on your machines | Sessions, Spaces (shared worktrees + knowledge base), ACP for third-party agents | PR review, replies to comments/CI | Human merge gate; enterprise ACUs |
| **Augment Cosmos** | Sandboxed cloud VMs, event-triggered (GitHub/Slack/Linear/PagerDuty/cron) | Automations, Experts, RBAC, HITL policies | Structural context engine (vendor claims ~33% fewer tokens) | SOC 2 / ISO 42001, escalation policies |
| **GitHub Copilot coding agent** | Ephemeral GitHub Actions environment | Assign an issue / `@copilot`; fleet view | Branch protection, Actions checks, draft PR | 59-minute session cap; human merge |
| **Google Jules** | Google Cloud VM per task | Task pool, plan-approve-PR | Plan approval, PR review | Up to 60 concurrent tasks on Ultra; Gemini only |
| **Claude Code (web + local)** | Local worktrees or Anthropic cloud sessions | Subagents, agent view, **agent teams** (experimental), **dynamic workflows** (JS script over many subagents) | Agent-run tests, adversarial cross-checks in workflows | Human review; permission modes; cloud auto-fix for CI/comments |
| **OpenHands (MIT)** | Local or Docker/remote workspace behind one API | Agent SDK + server, conversations, multi-LLM routing | Event-sourced state, deterministic replay, security analysis | Open-source, host it yourself |

Sources: [Factory 2.0](https://factory.com/news/software-factory),
[Droid 1.0](https://factory.com/news/frontier-harness),
[Claude Code parallel agents](https://code.claude.com/docs/en/agents),
[Claude Code workflows](https://code.claude.com/docs/en/workflows),
[OpenHands SDK paper](https://arxiv.org/html/2511.03690v2),
[cloud-agent comparison](https://agentatlas.dev/cloud-agents).

**Read for us:** the market has converged on *ephemeral worker per task* plus a
*queue* and a *review gate*. Our architecture is already that shape — one
branch per task, a merge queue, a single-run lock. The differences are scale
(many workers), context economics (routers, caching, compaction), and the
post-PR loop.

### 3. Spec-driven tooling

| Tool | Artifacts | Verification | Notable |
| --- | --- | --- | --- |
| **GitHub Spec Kit** (MIT) | `constitution.md`, then `spec.md` / `plan.md` / `tasks.md` (+ `research.md`, `contracts/`) | Clarify, checklist, analyze; **converge** loops until no gaps | 41 agent integrations; closest to our layout |
| **Kiro** (AWS, proprietary) | `requirements.md` (EARS), `design.md`, `tasks.md` | SMT-solver requirement analysis; property-based tests linked to requirements; parallel task waves | Strongest pre-code requirement checking |
| **BMAD / OpenSpec** | Skill-based planning, change folders | Structural validation, verify command | Lighter-weight, agent-agnostic |

Sources: [Spec Kit docs](https://github.github.com/spec-kit/),
[Spec Kit vs Kiro vs OpenSpec](https://qtrl.ai/blog/spec-kit-vs-kiro-vs-openspec).

**Read for us:** our SDD layout is already Spec-Kit-shaped (and predates the
converge step). We lack Kiro's two ideas: **requirements are checked for
ambiguity/inconsistency before planning**, and **acceptance criteria generate
executable evidence** (property tests), not just prose the coder may ignore.

### 4. Verification and evaluation

- **SWE-bench Verified is no longer a clean comparison.** OpenAI stopped
  evaluating on it in February 2026 after audits found flawed tests and
  contamination; the official board has no entry after 2026-02-26. Vendors
  still publish self-run scores. ([Cyborb, 2026-09-28](https://cyborb.ai/blog/coding-agent-leaderboard))
- **Terminal-Bench 4.0** is more harness-sensitive: the same model scores
  differently under Claude Code, Codex, Grok Build or mini-SWE-agent, and cost
  per attempt varies 4–10×. ([agent harness benchmark, 2026-11-05](https://www.aiagentsinfo.com/reports/agent-harness-benchmark-november-2026/pdf))
- **The useful pattern is a frozen task set you own**, replayed after every
  harness change, with success, cost and wall-clock per task. OpenHands ships
  this as the OpenHands Index; Factory reports cycle time and autonomy ratio.

**Read for us:** a public benchmark would not tell us whether *our* loop got
better at *our* specs. We need a small frozen replay set from this repo plus
the metrics we already record (`run.json`, `events.jsonl`, `shell_log.jsonl`).

## The autonomy ladder the market uses

The "dark factory" conversation has settled on a ladder rather than a switch:

1. **Assisted** — human writes, agent autocompletes.
2. **Delegated** — agent does a scoped task, human reviews the diff/PR.
3. **Milestone-gated** — agent runs the loop, human approves at PR/merge.
4. **Earned autonomy** — low-risk classes merge after machine gates; risk
   classes rise only when measured agreement/escape rates justify it.
5. **Dark factory (strict)** — humans write intent and checks; no human reads
   the diff, including for high-risk classes.

Two operational rules recur across the credible sources:

- **Risk classes 0–3** (docs/copy → core logic → auth/payments/infra/factory),
  computed as `max(spec-proposed, diff-computed)`; a policy bot is the required
  approver and merges only classes it has *earned*.
- **Escape-rate telemetry**: the share of changes that passed the gate and were
  later reverted/hotfixed. Autonomy is expanded or withdrawn on that number,
  not on vibes. Plus a drilled halt path and named incident ownership.

Sources: [O'Reilly, 2026-09-18](https://www.oreilly.com/radar/software-factories-light-and-dark/),
[Augment, 2026-09-17](https://www.augmentcode.com/guides/dark-factory-autonomous-software-delivery),
[Tim de Pater, 2026-10-28](https://timdepater.com/articles/blueprint-for-a-dark-factory/).

## Where our harness stands

### Baseline from `swarm/runs/` (2026-11-12)

| Metric | Value |
| --- | --- |
| Runs with `run.json` | 86 |
| Green | 54 (63%) |
| Cost per green task | mean **$0.0391**, median **$0.0206**, total **$2.11** |
| Fix-round rate (green runs with ≥1 fix round) | **59%** |
| Wall clock per green task | p50 **426 s** (~7 min), p90 **1663 s** (~28 min) |
| Stops (non-green) | `needs_human` 15, `crew_error` 8, `budget_exhausted` 8, `reviewer_blocked` 2, `reviewer_no_verdict` 2, `no_progress` 2, `preflight_failed` 1 |
| Biggest token consumers | QA **4.82M** prompt tokens; `coder:fix1` **3.22M**; `coder:fix2` **2.06M**; `coder:fix3` **1.50M** |

The economics are excellent (free-first routing works). The bottlenecks are
**wall clock, fix rounds, and the tail of human stops**.

### Strengths to keep (they are ahead of most of the market)

1. **Truthful green.** QA is the only gate executor; the harness records each
   execution in `shell_log.jsonl` and derives green from those records. Most
   market tools trust the agent's own test run.
2. **Layered verification.** 017 static self-check → 019 scenario verifier →
   QA gates → senior verdict repair. This is more rigorous than the common
   "agent runs tests and opens a PR".
3. **Spec discipline.** `spec.md` → `plan.md` → `tasks.md`, constitution, AC
   refs on every task, done ledger from commit trailers. Comparable to Spec
   Kit, ahead of most control planes.
4. **Recovery hygiene.** Plan cache by content hash, per-step `progress.json`,
   stash lifecycle + archive refs + conflict resolver, retry/backoff,
   supervisor, approval holds, branch-per-task + `--no-ff` merge queue with
   rollback, single-run lock, preflight on unmerged paths.
5. **Safety guards.** Scope + secret guards, argv-only shell, repo-only
   sandbox, no gates for coders, cost/token/time budgets, per-role fallbacks.
6. **Auditability.** `run.json`, `events.jsonl`, `shell_log.jsonl`,
   `human_log.txt`, TUI dashboard, commit trailers. This is close to what
   regulated buyers ask for, without OTel/provenance signing.

### Gaps, mapped to the market

| Dimension | Us | Market reference | Gap |
| --- | --- | --- | --- |
| **Execution concurrency** | One task at a time; steps run sequentially | Devin MultiDevin, Jules 60 concurrent, Claude dynamic workflows | No parallel steps, no multi-worker queue |
| **Context economics** | Full prompts re-sent; 3k coder read cap; no compaction/caching | Factory PTC; Anthropic caching/compaction; Augment context engine | 3.2M tokens on `fix1`, 4.8M on QA; loops from truncated reads |
| **Gate cost** | Full gate suite on every round | Test-impact selection is standard CI practice | No affected-test selection or gate-result cache |
| **Planning** | One planner, flat `STEP` list | Kiro parallel task waves; Spec Kit converge | Steps cannot run in parallel; no dependency graph |
| **Intake** | Human authors tasks; no spec lint | Kiro EARS + SMT; Spec Kit clarify/checklist/analyze | Vague briefs reach the coder; no bounce-with-questions gate |
| **Autonomy policy** | Green or human; approval hold | Risk classes 0–3, earned auto-merge, canary, halt drills | No risk classification or earned autonomy |
| **Post-PR loop** | Merge queue + conflict resolver | Devin/Copilot/Claude answer review comments and CI failures | Nothing after the merge |
| **Learning** | Lessons hand-written in `AGENTS.md` | Factory continual learning; Devin Spaces knowledge base | No automatic retrospective or retrieval |
| **Observability** | JSONL + local TUI | OTel gen-AI spans, provenance, dashboards, audit log | No spans, no signed provenance, no fleet view |
| **Scale** | Single repo, single machine, CLI triggers | Multi-repo fleets, event triggers (issues/Slack/CI) | No intake from trackers or CI |

## Growth opportunities

Impact is on the three requested axes; effort is rough (S ≤ 1 day,
M ≤ 1 week, H > 1 week of harness work). Risk is "new trust surface".

### Efficiency (cost, tokens, latency per green task)

| ID | Opportunity | Why (evidence) | Impact | Effort | Risk |
| --- | --- | --- | --- | --- | --- |
| E1 | **Prefix-stable prompts + provider prompt caching** — put system/tools/role text first, task data last, never mutate the prefix mid-run | Cache reads cost ~10% of input on Anthropic; stable prefixes also cut local prefill time | High | M | Low |
| E2 | **Context compaction + tool-result spilling** — summarise old rounds into durable task state; spill huge gate logs to a file with a locator instead of pasting | QA 4.8M prompt tokens; `fix1` 3.2M; compaction is the recommended long-run strategy | High | M | Medium (summary drift) |
| E3 | **Test-impact selection + gate-result cache** — map changed files to test targets; cache a gate result by content hash; run the full suite only on merge | Every fix round re-runs the full suite; p50 7 min / p90 28 min | High | M | Low |
| E4 | **Structured failure reports only** — the coder gets key lines + locators, not raw tails; the report is already 14k, make it semantic | Fix rounds spend tokens re-reading the same output | Medium | S | Low |
| E5 | **Whole-file/search reads for the coder where safe** — the verifier has `FullFileReadTool`; coders still stop at 3k and loop | 014-T1 re-read the same range 7× and ended `no_progress` | Medium | S | Low |
| E6 | **Programmatic tool calls for fan-out reads** — one model turn requests N files; the harness returns a filtered digest | Factory Droid 1.0 reports ~20% efficiency gain; Anthropic ~38% fewer input tokens on fan-out | Medium | H | Medium |

### Speed / throughput

| ID | Opportunity | Why | Impact | Effort | Risk |
| --- | --- | --- | --- | --- | --- |
| S1 | **Dependency-aware parallel micro-steps** — planner emits waves; independent steps run in isolated worktrees | Kiro already runs independent tasks in parallel waves; our steps are strictly sequential | High | H | Medium (merge/attribute) |
| S2 | **N concurrent task workers** — a real queue with per-provider rate limits; the merge queue already serialises integration | One task at a time caps throughput at ~2–4 tasks/hour | High | H | Medium (locks, cost) |
| S3 | **Warm start** — pre-plan and pre-scan the next task while the current one is in QA | Planning is 1–7 s, scanning is cheap; hides latency | Low–Med | M | Low |
| S4 | **Batch merge train** — merge several green branches per `--no-ff` integration round | The merge queue is one-at-a-time | Medium | M | Low |

### Autonomy

| ID | Opportunity | Why | Impact | Effort | Risk |
| --- | --- | --- | --- | --- | --- |
| A1 | **Spec intake gate** — lint ACs for testability, scope and cross-artifact consistency; bounce vague tasks with questions | Kiro's SMT analysis; Spec Kit clarify/checklist/analyze; our bad runs start with vague briefs | Med–High | M | Low |
| A2 | **Risk classes + earned auto-merge** — class 0/1 auto-merge after gates + verifier; class 2/3 human; measure agreement/escape rate | The credible dark-factory pattern; we already have the merge queue | High | M–H | Medium |
| A3 | **Post-PR loop** — answer review comments, fix CI on the PR, rebase | Devin/Copilot/Claude all do this; we stop at merge | High | H | Medium |
| A4 | **Stop-reason classifier + recovery crews** — turn `needs_human` into a targeted recovery attempt where the reason is mechanical | 15 `needs_human` + 8 `crew_error`; many are report/read/plan defects, not hard problems | Med | M | Medium |
| A5 | **Halt drills + incident ownership + escape-rate telemetry** — exercise the stop path, name an owner, measure post-merge reverts | Augment/Tim de Pater; a policy nobody exercised is a setting | Med | M | Low |

### Learning and trust (enablers)

| ID | Opportunity | Why | Impact | Effort | Risk |
| --- | --- | --- | --- | --- | --- |
| L1 | **Frozen benchmark set + replay + A/B** — 10–20 real tasks, fixed model/prompt, score green/cost/time/fix-rate | Without it, every change is anecdote; public benchmarks are saturated/contested | High | M | Low |
| L2 | **Run retrospective + memory retrieval** — auto-write a lesson per non-green run; retrieve relevant lessons into planner/coder prompts | Our lessons live in `AGENTS.md` and are read by humans, not by the next run | Med–High | M | Medium |
| O1 | **OTel gen-AI spans + signed provenance** — one span per crew/tool/gate; commit provenance | Market audit expectations; we already have trailers and logs | Med | M | Low |

## What not to copy

- **Autonomous production deploy.** No credible July-2026 source documents an
  agent deploying to production without human approval; even Factory keeps the
  merge/deploy policy human-owned. Our scope stops at merge.
- **A public benchmark score as the goal.** SWE-bench Verified is contested;
  Terminal-Bench mixes harness and model. Use a private replay set.
- **Unbounded agent teams / huge concurrency.** Token cost scales linearly and
  coordination overhead grows; start at 2–4 workers, not 60.
- **Full agent autonomy over the harness itself.** Risk class 3 includes the
  factory; keep harness edits human-reviewed (our `HARNESS_SPECS` already do).

## Proposed program (decision pending)

A coherent sequence, each phase independently valuable and measurable on L1:

| Phase | Spec | Scope | Success signal |
| --- | --- | --- | --- |
| 0 | **020-harness-efficiency** | L1 benchmark, E1, E2, E3, E4, E5 | Same green rate, ≥30% fewer tokens, ≥25% lower p90 wall clock |
| 1 | 021-parallel-factory | S1, S2, S4 | ≥2× tasks/hour at the same green rate |
| 2 | 022-earned-autonomy | A1, A2, A4, A5 | ≥50% fewer human stops; class 0/1 auto-merge with zero escapes |
| 3 | 023-closed-loop | A3, L2, O1 | Post-merge loop closes without a human restart; lessons retrieved |

The alternatives are: (a) one big spec covering all phases, (b) start with
autonomy (A2/A3) instead of efficiency, (c) start with parallelism (S1/S2),
(d) keep the harness as-is and only write the investigation.

## Decision points

These are the questions the spec must answer before it is written:

1. **Primary axis for the next spec** — efficiency, speed, autonomy, or the
   phased program above.
2. **Architecture stance** — stay on CrewAI Flow and harden it; introduce a
   durable event-sourced orchestrator with crews as workers; or evaluate a
   migration (LangGraph/Agent Framework) first.
3. **Autonomy envelope** — human merge gate for everything; earned autonomy
   for low-risk classes; or full auto-merge for green changes in this repo.
4. **Measurement** — is a frozen replay set part of the next spec (recommended)
   or a separate effort?

## Decisions (2026-11-12)

Answered by the operator before writing the spec:

1. **Primary axis — efficiency first.** Phase 0 is
   `specs/020-harness-efficiency/`: benchmark corpus, prefix-stable prompts +
   cache hints, compaction + spilling, test-impact gate selection, structured
   reports + coder search. Parallelism (S1/S2/S4) is 021; earned autonomy
   (A1/A2/A4/A5) is 022. Rationale: the measured waste (59% fix rate, 4.8M QA
   prompt tokens, 3.2M on `fix1`, every round running the full suite) is paid
   on every task, and it can be removed without adding a new trust surface or
   multiplying token spend the way concurrency would.
2. **Architecture stance — stay on the CrewAI Flow.** No framework migration
   and no event-sourced orchestrator in 020. The durable orchestrator layer
   (append-only journal, replay, resumable nodes, idempotent side effects) is
   recorded as a **good-to-have future option**, revisited after 021/022 prove
   the flow's limits at higher concurrency. Its shape, seams and promotion
   triggers are pinned in `docs/architecture/adr-012-orchestration-stance.md`.
3. **Autonomy envelope — earned autonomy by risk.** Class 0/1 (docs, tests,
   mechanical changes) may auto-merge after gates + the 019 verifier; class 2/3
   (core logic, auth, infra, the harness itself) stay human. Expansion and
   withdrawal are driven by measured agreement and escape rates, not by
   ambition. Not implemented in 020; it is 022's envelope.
4. **Measurement — the frozen replay set is inside 020** (T1 corpus + baseline
   snapshot, T7 live replay, T8 before/after table). Without it every later
   change is anecdote.

The exposure is deliberately unchanged by 020: same green definition (QA-only
evidence), same human merge gate, same harness-as-control-plane rule
(`HARNESS_SPECS`). 020 should make the loop cheaper, not more trusted.

## Results (020, in progress)

Same 12 frozen cases, same machine, no model call: `make swarm-bench` renders
the real prompt/report text and measures characters. Deltas are against the
T1 baseline (`swarm/bench/baseline.json`).

| After | Task prompt chars | Δ vs baseline | Report chars | Δ | Gates / round |
| --- | --- | --- | --- | --- | --- |
| T1 baseline | 461,763 (~115k tokens) | — | 41,456 | — | 60 |
| T2 prompt assembly | 488,177 (~122k tokens) | **+5.7%** | 41,456 | 0% | 60 |
| T4 compaction + spilling | 427,725 (~107k tokens) | **−7.4%** | 5,768 | **−86.1%** | 60 |
| T5 gate selection | 427,725 (~107k tokens) | −7.4% | 5,768 | −86.1% | **36 (−40%)** |
| T6 reports + search | 431,359 (~108k tokens) | **−6.6%** | 5,768 | −86.1% | 36 (−40%) |

### Live replay (T8): the offline win is real, the live green target is not met

`make swarm-bench-live CASE=004-weather-sun-T2` on the committed harness
(2026-11-12), with the operator's `.env` routing (OpenRouter free planner/senior,
local Ollama coder/QA) and no model pins:

| Metric | Historical green run (2026-11-09) | This replay (current harness) |
| --- | --- | --- |
| Status | green | **needs_human / `verifier_blocked`** |
| Wall clock | 125 s | **1050 s (17.5 min)** |
| Prompt tokens | 57k | **309k** |
| QA gate runs | 6 | **0** |
| Fix rounds (QA) | 0 | 0 |
| Repair rounds | 0 | **4** (2 self-check + 2 verifier) + 1 correction step |

What the loop produced: a 6-step plan for a one-file task; `app/preferences.py`
with only the two constants (the `get_preference` function never written); a
test file that imports the missing function, duplicates `def test_get_preference`,
and asserts the *opposite* mapping from the AC. The 017 self-check caught it
(mypy `attr-defined`/`no-redef`, ruff `I001`/`F811`), spent two fix rounds
(78.5k prompt tokens each) and changed nothing; the 019 verifier then blocked
with 7 findings, its two correction steps ran (42.7k), and it blocked again
(3 findings) → `needs_human` after the round budget.

**Verdict for 020 AC-7:** the offline targets hold (prompt −6.6%, report −86.1%,
gates −40%), but the "same green status on a live replay" target is **missed**
on this case. This is not a 020 regression: the run never reached QA, so the
compaction/selection/cache behaviours did not participate. It is the fix-loop
problem 021 specifies — over-decomposed plan, a coder-written test that encodes
the wrong behaviour, and repair rounds that cannot fix a missing function. The
"off" A/B for this case is recorded as **not applicable**: with no QA round and
no gate evidence, the 020 switches have nothing to change.

The replay is also model-confounded (local coder vs the historical paid/free
mix), which is why 021's suite pins models and compares per case rather than
against history.

**T4 reading.** The step digest and the gate-log spilling remove the two
things that grew with every failed round. The report delta is the large one
(−86%): a 3k failing tail becomes a handful of `file:line: message` key lines
plus a path, and the full text is still in `<run>/gate_logs/`. Task prompts
fall 7.4% net, but unevenly: a case with one step and zero fix rounds is still
slightly above baseline (the T2 brief cost) because compaction has nothing to
remove there. Gate count is untouched — that is T5.

**T7 reading.** A live replay is the only number that proves the offline win is
real. It runs one frozen case in a worktree at `green_sha^` with the current
harness, pinned models and no commit, and reports status/tokens/wall clock/fix
rounds. It is opt-in because it needs models; T8 records what it measured.

**T3 reading.** Our routes (Ollama, OpenRouter) cache an identical prefix
automatically; the hint path exists for a direct Anthropic model and falls back
to a plain call when a provider rejects the field. That is why the character
numbers do not move at T3: caching changes what those characters *cost*, and
`run.json.cache` plus `usage.cached_prompt_tokens` are where the effect is read.

**T6 reading.** Reports now carry one form of the failure: key lines, plus the
spilled-log path when there is more. The raw tail is a fallback for output that
extraction cannot parse. The prompt is 3.6k chars above T5 because the search
tool's description rides in every coder prompt; that is a deliberate trade for
killing the 014-T1 re-read loop (229 calls, `no_progress`), and the description
is kept to one line.

**T5 reading.** Selection is measured on the same cases: every one resolves
to a single area (backend or frontend), so the inner loop asks for 3 commands
instead of 6. The full suite still gates green, so the saving is latency and
not correctness: QA runs it once, at the final delta, and the harness refuses a
green whose last round was the selected subset. The metric is inner-loop gates
per round; the end-to-end wall-clock effect needs T7's live replay.

**T2 reading.** Prompts are now byte-stable per task and role: the brief and
fixed rules form one cacheable head, and the volatile step/report/summary comes
last. The +5.7% is the brief, which the old step prompt never carried (it was
passed only to the planner/QA/fix crews); it is charged per step and is the
content that makes a step self-contained. The prefix is what provider caching
and Ollama KV reuse can discount in T3 — the character count alone is not the
metric that should move here. T4 (compaction/spilling) and T6 (structured
reports) are where the net reduction has to come from; the −30% target is
judged at T8, not here.
