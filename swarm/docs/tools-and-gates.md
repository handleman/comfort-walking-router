# Guarded tools and gates

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Agent tools (guarded, `swarm/tools_guarded.py`)
- `Repo Edit` — exact-match replace, exactly-once occurrence required, repo jail, **coder-scope check**, secret-path refusal.
- `Repo Create` — new files only (makes parent dirs, refuses existing/escapes), **coder-scope check**, secret-path refusal. Scaffold needs it: without it the coder cannot create `app/__init__.py` et al.
- `Guarded Shell` — argv-only (`shlex.split` + `shell=False`, never `shell=True`): `pytest`, `ruff check` (including `--fix`), `mypy` (gates); `git status|diff|log` (read-only); `ls`, `cat`, `grep` (read-only inspection, no recursive grep); `npm --prefix frontend run check|build|lint|test`, plus `run format` (deterministic Prettier autofix in fix rounds). Rejects shell metacharacters, absolute paths, `..`, `.env*`/key files, `npm install`/`npx`, `pip`/`uv`, and `python -c`. 120 s timeout, repo cwd (300 s for the browser suite). The suite is argv-exact — `npm --prefix frontend run test:e2e [-- e2e/x.spec.ts]`, no flags, so a run cannot narrow it — and QA-only: it is the execution 026 requires for a task whose brief names `frontend/e2e/*`. It must be the npm *script* form: `run` gives Playwright cwd=`frontend/`, so `playwright.config.ts` (baseURL, fixture backend, `vite preview`) loads; the `exec` form keeps the repo cwd and fails every test on `page.goto('/')`. Coder crews construct it with `allow_gates=False` (QA-only gates); fix crews and the Reviewer get `allow_gates=True`.
- Read-only: trimmed file reads (3000 chars max) with the same secret/path guard for coders and QA; the scenario verifier (019) uses `FullFileReadTool` (whole files, `SWARM_VERIFY_READ_CHARS`, default 60000); `ls` via Guarded Shell (no directory-search tool).

## Gates (sequence)
Planner splits the task into `STEP n:` micro-steps → one fresh coder per step (fresh
context each, max 8 steps) → **the harness runs the static checks (types, lint) and
gives a red one back to the coder** → **the scenario verifier reads the whole
scenario (brief, ACs, plan, full delta files, import graph) and blocks a brief
that was not implemented** → Reviewer verifies once at the end → QA runs every
command from `SWARM_GATE_COMMANDS` (this repo: `pytest -q`, `ruff check .`,
`mypy app tests`, `npm --prefix frontend run check`,
`npm --prefix frontend run lint`), and the flow derives green from those
recorded executions — never from agent prose (see *Gate ownership* below). Red
gates or a reviewer `BLOCKED` → fix
round: Coder investigates with the QA report (+ Reviewer re-verify), max 3 rounds
(`MAX_FIX_ROUNDS` in `swarm/crew.py`). Still red → `needs_human`, TUI pauses,
`r` starts a fresh run. Crash → one fresh re-kickoff, then `crew_error`.

### Gate ownership (who runs what)

- **QA (Reviewer) is the only agent that runs gates.** It executes
  `SWARM_GATE_COMMANDS`, pastes exit codes + tails, and ends with
  `VERDICT: PASS`/`BLOCKED`.
- **Coders never run gates during development.** Their `Guarded Shell` is built
  with `allow_gates=False` and answers `BLOCKED: gates are QA-only`. A fix round
  starts only after QA `BLOCKED` (or red flow gates); then the coder gets
  `allow_gates=True` plus the QA report and may reproduce/confirm the fix
  (`VERIFY_RULE`/`MAX_FIX_VERIFY_CYCLES` in `swarm/crew.py`) and keeps fixing until
  every gate it ran is green (3 cycles max). This keeps QA the single verification owner
  without spending coder tokens on duplicate gate calls.
- **The harness records what QA actually ran** (015 AC-2). Every `Guarded Shell`
  execution appends `{agent, argv, exit, duration_ms, changed_after, tail}` to
  `<run>/shell_log.jsonl`. The flow computes green from those records: each
  command in `SWARM_GATE_COMMANDS` needs a QA execution at the *current* in-scope
  hash. Model prose is never the source of an exit code, so dropping the flow's
  own gate run does not weaken truthful green. A missing or stale record is
  `reason_code=qa_gate_missing`, never green. `SWARM_TRUST_QA_EVIDENCE=0` restores
  the 012 behaviour (flow re-runs gates) for debugging.
- **Only a declared verdict counts.** `reviewer_verdict` accepts a `VERDICT: PASS|BLOCKED`
  line, a JSON `{"verdict": …}`, or a standalone final word — never the word
  "BLOCKED" from the reviewer's reasoning. A review that runs out of iterations
  is `reviewer_no_verdict` (one clean verdict-only retry, then human), not a block.
- **Stalled blocks stop early.** With every gate green, a round that changes no
  files (`no_progress`) or a block that cites nothing checkable
  (`reviewer_blocked_ungrounded`) ends the loop instead of paying for more coder
  rounds; a grounded block (test id, file:line, failing command, AC) keeps looping.
- **A dead endpoint fails over, not over and over.** Cloud calls use a 60 s request timeout and one SDK retry; a transport failure gets one same-model retry, and a second identical failure switches to the configured fallback models. Measured on `zen/glm-5.3-flash`: 40k-token prompt → 2.7 s, big prompt + tools → 3.5 s, so timeouts are transport stalls, not slow generations.
- **Prices come from the provider.** `zen/glm-5.3-flash` is $0.15/M in, $0.50/M out (reasoning tokens are billed as output); the earlier $0.10/$0.30 table under-reported by ~50%. `estimate_cost` uses the re-measured table.
- **The coder gets QA's evidence.** `run.json.qa_report` (and the fix prompt)
  contains per gate: argv, exit code, and the failure output — failing test ids,
  lint rules, type errors — plus the changed-file list. Rounds are QA→coder→QA,
  max 3 (`MAX_FIX_ROUNDS`); the coder never re-runs a gate.
- **The failure output comes first.** The report lists the *failing* gates first,
  each with its exit code, its raw output and a compact list of key lines
  (`file:line: message`) extracted from the tail; passing gates are one line
  each. 007-T9 (2026-11-10) lost its vitest failure to the old 9000-char
  report cap, so the coder "fixed" a file it never saw. The budget is now
  14k chars with a 3k tail per failing gate (`swarm/evidence.py`).
- **A style-only failure is repaired by the harness, not by a coder round.**
  When the *only* red gate is a lint/format gate and its output names nothing
  but formatting (`prettier`, or an ESLint rule that `eslint --fix` repairs),
  the flow runs `SWARM_STYLE_FIX_COMMAND` (this repo:
  `npm --prefix frontend run lint:fix`), re-checks the gate, and reverts files
  the formatter touched that the run does not own. A red type check or a red
  test is never treated as style — that is a code problem. `SWARM_STYLE_FIX=0`
  disables it; `run.json.style_autofix` records what ran.
- **The coder checks types and lint before QA sees the work (017).** Right
  after the micro-steps the harness runs the project's *static* checks — the
  type checker and the linter, never the test suites (`SWARM_SELF_CHECK_COMMANDS`,
  or the static subset of `SWARM_GATE_COMMANDS`: here `ruff check .`,
  `mypy app tests`, `npm --prefix frontend run check`,
  `npm --prefix frontend run lint`). A red check produces a report in the same
  shape as QA's (failing command, exit code, `file:line: message` key lines)
  and the coder gets a fix round with it (`MAX_SELF_CHECK_ROUNDS`, coder only,
  no gates), so a one-line type error is fixed while the work is still his.
  007-T9 (2026-11-11) spent three QA rounds and two coder rounds on
  `Property 'tick' does not exist on type 'PositionProvider'` — an error the
  checker had already named. The phase is *not* a gate: it runs under its own
  agent role (`harness-selfcheck`), so its records are never counted as QA
  evidence and it can never make a run green. `SWARM_SELF_CHECK=0` disables it;
  `run.json.self_check` records the commands, their exit codes and the rounds.
- **A fix round that changes nothing ends the round.** If a fix round leaves the
  in-scope delta byte-identical, the flow stops the round (`no_progress`) and
  escalates instead of paying for another identical attempt.
