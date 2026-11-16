# 019 Scenario Verifier — Plan

Status: proposed. References `specs/019-scenario-verifier/spec.md` AC-1–AC-9.

## Approach

A new phase in the flow, between the 017 self-check and QA:

```
micro-steps → self-check (017) → VERIFY round 1
                                   ├─ PASS  → QA (gates) → fix rounds → VERIFY (if the delta changed)
                                   └─ BLOCKED → correction steps (coder crews) → VERIFY round 2
                                                                        ├─ PASS  → QA …
                                                                        └─ BLOCKED → verifier_blocked (needs_human)
```

The verifier is a **read-only crew** with its own model role, its own whole-file
read tool and its own verdict. It never writes, never runs a gate and never
decides green — QA still owns the gates. What it adds is the one question the
loop never asked: *does the implemented scenario do what the brief says?*

The correction plan is written in the planner's own format, so the loop needs
no new machinery to execute it: `crew.STEP_RE` already parses `STEP n: …`
lines and `flow._resolve_steps` already turns them into a step list. The
correction steps are executed by the existing `build_step_crew` (scope rules,
delta attribution, a fresh message history per step), and the verifier runs
again.

### The scenario context

The harness builds the verifier's prompt from the run, not from the model:

- the task brief and its `ac_refs` (from `specs/<spec>/tasks.md`),
- the acceptance criteria paragraphs those refs point at (from `spec.md`),
- the `plan.md` lines that mention the task's files (the plan section),
- the **full content** of every file in the run delta (in-scope paths),
- a **connection view**: for each delta file, the repo-relative paths it
  imports and the repo-relative paths that import it.

The connection view is a dependency-free static scan (Python `from x import y`
/ `import x`; TS/Svelte `from '…'`, `import … from '…'`, `require('…')`). It is
best-effort and labelled as such in the prompt — a missing edge is a hint, not
a proof. It is what lets the verifier see a duplicate implementation
(`frontend/src/lib/navigation/walkMode.ts` next to the real
`frontend/src/lib/walkMode.ts`) or a contract that the code drifted away from.

### What the verifier may and may not do

| | the verifier | the coder crews |
| --- | --- | --- |
| read files | yes, whole files (`FullFileReadTool`) | yes, trimmed to 3000 chars |
| write files | **never** (no `Repo Create`/`Repo Edit`) | yes, in scope |
| run gates | **never** (`allow_gates=False`) | never either — QA owns the gates |
| commit / push | never | never — the harness does that |
| produce text | verdict + findings + correction plan | the diff summary |

The correction plan is the crew's **final answer**, parsed by the harness —
exactly like the planner's `STEP n:` lines and QA's `VERDICT:` line. No
verifier output is ever written into the repository by the verifier itself.

## Modules

### `swarm/verify.py` (new)

- `MAX_VERIFY_ROUNDS = 2`, `MAX_VERIFY_FILES = 12`, `MAX_CONTEXT_CHARS = 60000`,
  `MAX_PLAN_STEPS` = the planner's `MAX_STEPS` (8).
- `scenario_context(repo_root, spec_dir, task, changed) -> dict` — the bundle
  above. The whole content of the delta files is included up to
  `MAX_CONTEXT_CHARS`; the files that did not fit are listed by name and size
  so the verifier knows they exist.
- `ac_paragraphs(spec_md, ac_refs) -> list[str]` — the `- [ ] AC-n: …` lines
  the task references.
- `plan_lines(plan_md, task, changed) -> list[str]` — the plan lines that
  mention a file of this task (best-effort).
- `connections(repo_root, paths) -> dict[str, dict[str, list[str]]]` — the
  import/imported-by view.
- `parse_verdict(text) -> tuple[str, list[str]]` — `("pass"|"blocked", findings)`
  from `VERDICT:` and `FINDING:` lines.
- `parse_plan(text) -> list[str]` — the correction steps, reusing
  `swarm.crew.STEP_RE` so the format has exactly one definition.
- `render_report(context, findings, plan) -> str` — the bounded report the
  coder receives with the correction plan.

### `swarm/tools_guarded.py`

- `FullFileReadTool(TrimmedFileReadTool)` — the verifier's read tool. The cap
  comes from `SWARM_VERIFY_READ_CHARS` (default 60000) instead of the fixed
  3000. When a file is larger than the cap the tool says so by name and size
  and where to continue, instead of returning a head that looks complete.
  The path/secret guard is inherited unchanged.

### `swarm/crew.py`

- `build_verify_crew(spec_dir, task, context_text) -> Crew` — the "Scenario
  Verifier" agent: `FullFileReadTool` + `ShellTool(allow_gates=False,
  agent_role="verifier")` (read-only inspection only: `ls`, `cat`, `grep`,
  `git status|diff|log`), **no** write tools. `max_iter` 12.
  The prompt asks the scenario questions (does every element the brief names
  exist? do the pieces connect? are the ACs addressed?) and fixes the output
  format: `FINDING: <file/lines> — <what is wrong>` lines, then `STEP n: <file>
  — <one precise action>` correction steps, then `VERDICT: PASS` or
  `VERDICT: BLOCKED`. That final answer *is* the deliverable — the crew
  writes nothing else.

### `swarm/llms.py`

- `verifier_llm()` + `SWARM_VERIFIER_MODEL` (default: the senior/free model —
  the verifier has to reason, not count) and `SWARM_VERIFIER_FALLBACK_MODEL`.
  The role joins `ROLE_MODEL_VARS` so the dashboard shows it.

### `swarm/flow.py`

- `SwarmState.verifier: dict[str, Any]` — verdict, rounds, findings, plan,
  files read, model.
- `_verify_phase(task, changed, kick) -> bool` — mirrors `_self_check_phase`:
  build the context, kick the verifier crew, parse the verdict; on `BLOCKED`
  parse the correction plan and execute those steps with `build_step_crew`
  (role `coder:verify<n>`), then verify again, up to `MAX_VERIFY_ROUNDS`.
  Returns whether the scenario holds.
- The call site: after `self._self_check_phase(...)` in `run_crew`, and again
  after a fix round that changed the delta signature.
- `verifier_blocked` joins the non-green statuses; a run that ends with an
  unresolved verdict stops as `needs_human` with `reason_code =
  "verifier_blocked"` — never an unbounded loop.
- `HARNESS_SPECS` gains `019-scenario-verifier`.
- `_fallback_key` maps the `verifier` role to `SWARM_VERIFIER_MODEL`.

### `swarm/humanlog.py`, `swarm/tui.py`

- The human report and the dashboard show the verifier's verdict and its
  findings next to QA's verdict — one renderer, so they cannot drift (the 018
  rule).

## Steps

1. `swarm/verify.py` + `swarm/tests/test_verify.py`: the context builder
   (brief, ACs, plan lines, whole-file delta, connection view), the bounds,
   the verdict/plan parsing.
2. `FullFileReadTool` in `swarm/tools_guarded.py` + its tests.
3. `build_verify_crew` in `swarm/crew.py` and `verifier_llm()` in
   `swarm/llms.py` + `.env.example` (`SWARM_VERIFIER_MODEL`,
   `SWARM_VERIFY`, `SWARM_VERIFY_READ_CHARS`).
4. `_verify_phase` in `swarm/flow.py`: the phase, the hand-back into the
   coder loop, the bounds, `run.json.verifier`, `verifier_blocked`.
5. `swarm/humanlog.py` + `swarm/tui.py`: show the verdict.
6. Docs: `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`, `changelog.md`.
7. Gates: `make swarm-test`, `make lint`, `make typecheck`.

## Risks / Open Questions

- **Cost.** The verifier is another crew per task. It runs on a free local
  model by default (`SWARM_VERIFIER_MODEL`), reads at most `MAX_VERIFY_FILES`
  files and stops after `MAX_VERIFY_ROUNDS` rounds, so the worst case is two
  bounded rounds per task. Its usage is attributed to its own role and counts
  against the same task budget as the other crews.
- **False blocks.** A verifier that blocks on style or taste would cost a
  coder round. The prompt therefore asks only about the brief, the
  connections and the referenced ACs — the same ground the QA Gatekeeper
  covers (gates), not the ground it does not (taste). A blocked verifier with
  no `FINDING:` line is treated as a pass, and an ungrounded block ends the
  round instead of looping.
- **The connection view is a heuristic.** A dynamic import or a path alias
  will not appear. It is presented as a hint, and the prompt tells the
  verifier to verify a suspected duplicate by reading both files.
- **Ordering.** The verifier runs before QA, so a false green is caught
  before the gates are run — but the gates still decide green. A run whose
  verifier blocks and whose correction steps do not converge ends as
  `needs_human`, which is the honest outcome.
