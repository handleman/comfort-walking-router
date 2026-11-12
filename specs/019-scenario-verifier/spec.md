# 019 Scenario Verifier — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

The swarm's notion of "green" is *the gates passed*. That is a statement about
the code that exists, not about the task that was asked for. Six 014 tasks
were committed green by the swarm — T2, T3, T4, T5, T7 and T8. Three of them
do not do what their brief says, and two further tasks never landed at all:

| task | the brief asked for | what actually landed |
| --- | --- | --- |
| 014-T2 | `GET /geocode` and `GET /geocode/reverse` in `app/main.py`, `contracts/geocode.json`, validation, a 5-minute cache | `app/cache.py` + `contracts/geocode.json` — **no endpoint in `app/main.py`** (commit `c221014`) |
| 014-T7 | `frontend/src/lib/search/suggestions.ts` + `SearchInput.svelte`, with vitest coverage | a client for `/api/geocode/suggest` reading `results` — while the pinned plan says `/geocode` reading `suggestions` — and **no test file** (commit `1e5d770`) |
| 014-T8 | wire selection *and map picks* in `App.svelte` | `App.svelte` sends `start_coords` — but no selection UI is wired and there is no pick mode (commit `98ddab9`) |
| 014-T6 | pick buttons next to Start/End plus `frontend/src/lib/map/picker.ts` | **nothing** — there is no T6 commit at all |
| 014-T9 | `frontend/src/lib/components/ArrivalCard.svelte` on the 25 m arrival signal | **nothing** |

Every one of those runs was green. The gates were green because the gates
test the code that exists: a missing endpoint produces no failing assertion,
so `pytest -q → 0`, `ruff → 0`, `mypy → 0`, and QA's verdict is `PASS`.

Three properties of the harness make the gap unclosable today:

1. **Nobody asks the scenario question.** The only verifier is the QA
   Gatekeeper, and its verdict is per gate: "the command exited 0". It never
   compares the implementation against the brief, the acceptance criteria, or
   the plan.
2. **The verifier cannot see the whole scenario.** Every observation is
   truncated at 3000 characters (`TrimmedFileReadTool` in
   `swarm/tools_guarded.py`) — for the coder *and* for QA. 014-T1 asked for
   lines 1–500 of a 178-line file seven times and saw the same first 85 lines
   every time; it never saw line 169.
3. **The loop can only repair what a gate proves broken.** The QA report is
   per-gate exit codes plus failure output. A *missing* piece — an endpoint
   that was never created — has no failing test, so the fix round has nothing
   to work from. It edits a file that was never wrong, the delta does not
   change, and the run ends `no_progress`.

And the connections between the files stay invisible: 007-T9 wrote its own
`frontend/src/lib/navigation/walkMode.ts` while the real store was
`frontend/src/lib/walkMode.ts`, and the test passed against the duplicate.
Only a reader that sees both files — and the import graph around them — can
catch that.

## Goal

One general verifier per task that reads the **whole scenario** and hands the
loop a **correction plan** when the scenario does not hold.

It runs when the task's micro-steps are ready (and again after a later change
to the delta), sees the brief, the acceptance criteria, the plan, the full
content of every file the run touched and the import connections around them,
and answers one question: *does the implemented scenario do what the brief
says, end to end?*

If the answer is no, it does not fix anything itself — it *emits* a correction
plan in the planner's own `STEP n:` format, and the flow feeds that plan back
into the coder loop, exactly like a QA-driven fix round.

**"Read-only" means the repository is read-only.** The verifier never writes a
file: no `Repo Create`, no `Repo Edit`, no gate execution, no commit, no
push. What it produces is *text* — its final answer, which the harness parses.
That is not a special case: the planner emits `STEP n:` lines as text (it has
no write tools either) and QA emits `VERDICT: PASS|BLOCKED` as text. The
verifier's plan is the same kind of artefact — a proposal, not an edit. The
coder crews apply it; the working tree changes only because the coder wrote
to it.

## Acceptance criteria

- **AC-1** — The verifier runs when the task's micro-steps are ready: after
  the last micro-step and the 017 self-check, and again after any later
  change to the run delta (a QA-driven fix round). `SWARM_VERIFY=0` disables
  the phase.
- **AC-2** — The verifier sees the whole scenario: the task brief, the
  acceptance criteria it references (from `spec.md`), the relevant `plan.md`
  section, the **full content** of every file in the run delta, and a
  connection view — for each delta file, the repo paths it imports and the
  repo paths that import it. The connection view is best-effort static
  analysis and says so.
- **AC-3** — The verifier reads whole files. It has its own read tool, whose
  observation cap is configurable (`SWARM_VERIFY_READ_CHARS`, default 60000)
  and is *not* the coder's 3000-character trimmed read. A file that is still
  larger than the cap is reported by name and size — never silently returned
  as a head. The coder keeps the trimmed read (small models lose the plot in
  a flood of context).
- **AC-4** — The verdict is about the scenario, not about the gates. The
  verifier checks that every element the brief names exists, that the pieces
  connect (the endpoint is mounted; the component imports the real module
  instead of a copy; the contract and the code agree), and that the
  referenced acceptance criteria are addressed. It answers `VERDICT: PASS` or
  `VERDICT: BLOCKED`, with one `FINDING:` line per problem.
- **AC-5** — A blocked verifier produces a correction plan in the planner's own
  format — `STEP n: <file> — <one precise action>` — so the flow reuses the
  existing step machinery (scope rules, delta attribution, a fresh message
  history per step). The plan is bounded by the same `MAX_STEPS` budget as
  the original plan.
- **AC-6** — The plan goes back into the loop. The flow executes the
  correction steps with the coder crews and re-verifies, bounded by
  `MAX_VERIFY_ROUNDS` (2). A verifier that does not converge ends the run as
  `verifier_blocked` (non-green, `needs_human`) with a copyable reason — it
  never loops.
- **AC-7** — The verifier cannot change the repository: no write tools
  (`Repo Create`/`Repo Edit`), no gate execution, its own agent role
  (`verifier`), so its shell records are never QA evidence and a verifier
  `PASS` can never make a run green. Its only output is text — the verdict
  and, when blocked, the correction plan the coder crews execute. QA still
  owns the gates.
- **AC-8** — Every round is recorded and visible: `run.json.verifier` holds
  the verdict, the rounds, the findings, the correction plan, the files read
  and the model; `human_log.txt` and the dashboard show the verifier's
  verdict next to QA's.
- **AC-9** — The phase is bounded and inside the run's budget: rounds, files
  per round, context characters and plan size all have ceilings, and the
  verifier's usage is attributed to its own role like every other crew.

## Non-goals

- Not a replacement for QA: the verifier never runs a gate and never decides
  green. QA's gates remain the only evidence of green.
- Not a linter or a type checker — that is the 017 self-check, which runs
  earlier and cheaper.
- Not a second coder: it never edits files, it plans; the coder applies the
  plan.
- Not a whole-spec audit: one task's scenario at a time. The other tasks of
  a spec are separate runs with their own verification.
- No new state store: everything lands in the existing `run.json`,
  `human_log.txt` and the existing dashboard screens.
