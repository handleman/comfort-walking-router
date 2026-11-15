# How the swarm organizes the work

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## How the swarm organizes the work

One task at a time: a `- [ ] T<n>` line from `specs/*/tasks.md` that the done
ledger does not already hold. Each phase is a small CrewAI crew with its own
model role; a CrewAI Flow (`swarm/flow.py`) sequences them and owns every
decision that must not be made by a model (retries, scope, green, commit).

### Roles

| Role | Model env | Job | Can make a run green? |
| --- | --- | --- | --- |
| Planner | `SWARM_PLANNER_MODEL` (paid allowed) | Reads spec + plan, emits `STEP n:` lines | no |
| Test author (optional, `SWARM_TESTS_FIRST`) | coder | Writes failing tests per AC, no implementation | no |
| Coder (step crews) | `SWARM_CODER_MODEL` (local for trivial, paid for real) | One micro-step per crew: read → edit | no |
| Self-check | `harness-selfcheck` (harness role, no model) | Runs static checks (types/lint), hands a red one back as a bounded fix round | no (never QA evidence) |
| Verifier | `SWARM_VERIFIER_MODEL` | Read-only: does the scenario do what the brief says? `VERDICT: PASS/BLOCKED` + `FINDING:`/`STEP n:` | no (advisory, blocks only) |
| Correction crew | senior | Executes the verifier's `STEP n:` plan (role `coder:verify<n>`) | no |
| QA Gatekeeper | `SWARM_REVIEWER_MODEL` | The only agent that runs the gates; records argv/exit/output in `shell_log.jsonl`, then declares `VERDICT: PASS/BLOCKED` | **yes** — green = QA evidence + PASS |
| Fix coder / senior fix | coder / senior | Works from QA's report (`file:line: message`, failing gates first) | no |
| Conflict resolvers | conflict model | Merge conflict, stash conflict | no (gates decide) |

### The sequence

1. **Preflight** — models, keys, venvs, gate binaries, Playwright browsers, the
   crews' real role factories. Fail before the first LLM call.
2. **Plan** — the planner emits `STEP n:` lines (cached, content-hashed,
   vacancy-checked).
3. **Micro-steps** — one coder crew per step; routing picks local vs paid;
   transient failures are retried by the harness (agents have
   `max_retry_limit=0`).
4. **Delta guard** — model-free: empty delta → `no_delta`; a brief-named file
   never created → `delta_incomplete`. Stop before any judge is paid.
5. **Self-check** — static checks; red goes back to the coder as a bounded fix
   round.
6. **Verifier** — read-only scenario check over the brief, the referenced ACs,
   the plan lines, the full delta files and the import graph. `BLOCKED` →
   correction crews → re-verify, bounded. A correction that turns a green static
   check red is reverted (`correction_reverted`).
7. **QA** — runs the gates, judges the work, declares the verdict. The budget
   never blocks it: it decides work already paid for.
8. **Fix loop** — QA→coder→QA, max 3 rounds, then senior escalation. A round
   that changes nothing (`no_progress`) or the same failure signature ends the
   loop.
9. **Green gate** — only when every gate exits 0, the reviewer says `PASS`, the
   verifier is not blocked, e2e evidence exists when the brief names
   `frontend/e2e/*`, and the run was not started with `--require-approval` (the
   one hold that exists). Then: branch per task → gates → `--no-ff` merge queue →
   commit with trailers (`Swarm-Task`, `-Task-Hash`, `-Spec-Hash`, `-Run`) →
   push. Green-but-unconfirmed (a selected subset only) is `needs_human`.
10. **Record** — `run.json`, `events.jsonl`, `shell_log.jsonl`, `progress.json`,
    the journal, `human_log.txt`, the done ledger.

### Flow

```mermaid
flowchart TD
    Q["Queue: next open task<br/>spec/tasks.md - ledger - parked"] --> P["Preflight<br/>models / keys / venvs / gates / e2e"]
    P -->|"fail"| PF["preflight_failed or config_error<br/>run.json.error"]
    P --> PL["PLANNER crew<br/>STEP n: plan"]
    PL --> TF{"tests-first?<br/>SWARM_TESTS_FIRST=1"}
    TF -->|"yes"| TA["TEST AUTHOR crew<br/>failing tests per AC"]
    TF -->|"no"| C
    TA --> C["CODER step crews<br/>one micro-step each<br/>local for trivial, paid on retry"]
    C --> DG{"DELTA GUARD<br/>empty? brief files created?"}
    DG -->|"red"| NH1["needs_human<br/>before any judge is paid"]
    DG -->|"ok"| SC["SELF-CHECK (harness role)<br/>types + lint"]
    SC -->|"red: bounded fix round"| C
    SC -->|"green"| V["VERIFIER crew (read-only)<br/>brief / ACs / plan / full delta / imports"]
    V -->|"BLOCKED + STEP n:"| CC["CORRECTION crews (senior)<br/>coder:verify n"]
    CC --> CG{"correction guard<br/>static check green to red?"}
    CG -->|"yes: revert that step's paths"| NH2["correction_reverted"]
    CG -->|"no"| V
    V -->|"unknown after 1 repair"| NH3["needs_human<br/>judges.verifier.terminal"]
    V -->|"PASS"| QA["QA GATEKEEPER - the only gate runner<br/>shell_log.jsonl + VERDICT"]
    QA -->|"unknown verdict"| NH4["needs_human<br/>judges.qa.terminal"]
    QA --> G{"gates all 0 AND verdict PASS AND<br/>not verifier-blocked AND<br/>e2e evidence if required"}
    G -->|"no, fix rounds < 3"| F["FIX coder / SENIOR crew<br/>works from QA report"]
    F --> QA
    G -->|"no"| NH5["needs_human<br/>no_progress / evidence_note"]
    G -->|"yes"| AU{"--require-approval<br/>on this run?"}
    AU -->|"yes: hold"| AP["awaiting_approval<br/>dashboard a / make swarm-approve"]
    AP --> BR
    AU -->|"no"| BR["branch per task, then gates, then<br/>--no-ff merge queue"]
    BR -->|"conflict or failed gate"| MF["merge_failed<br/>patch reversed, task stays open"]
    BR --> CM["commit with trailers<br/>Swarm-Task / -Task-Hash / -Spec-Hash / -Run"]
    CM --> PU["push (best effort)"]
    PU --> R["run.json / events / journal /<br/>human_log.txt / done ledger"]
```

### The invariant that shapes everything

- **Green is QA's, not the model's prose.** Gate exit codes come from
  `shell_log.jsonl`; the verifier, self-check and correction crews run under
  their own roles, so their executions can never be counted as QA evidence.
- **Deterministic guards sit around the judges, not inside them.** They stop
  with typed reason codes (`no_delta`, `delta_incomplete`, `correction_reverted`,
  `e2e_missing`, `quota_exhausted`, `wall_budget`, `verifier_blocked`) and none
  of them can make a run green.
- **One retry authority.** The harness retries, falls back and backs off; agents
  retry zero times (`max_retry_limit=0`).
- Several independent tasks can run at once via `make swarm-parallel` (detached
  worktrees, `--no-commit`), but integration is serial with the main tree as the
  single writer.
