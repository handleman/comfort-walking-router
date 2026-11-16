# 019 Scenario Verifier — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [x] T1 (AC-2, AC-9): add `swarm/verify.py` — the scenario context builder:
  the task brief, the `AC-n:` paragraphs its refs point at, the `plan.md`
  lines for the task, the **full content** of every in-scope file in the run
  delta, and a connection view (per delta file: the repo paths it imports and
  the paths that import it) from a dependency-free static import scan.
  Bounded by `MAX_VERIFY_FILES` (12) and `MAX_CONTEXT_CHARS` (60000); a file
  that does not fit is listed by name and size, never silently dropped.
  Evidence: `swarm/verify.py`, `swarm/tests/test_verify.py`.
- [x] T2 (AC-3): add `FullFileReadTool` to `swarm/tools_guarded.py` — the
  verifier's whole-file read, cap from `SWARM_VERIFY_READ_CHARS` (default
  60000), path/secret guard unchanged; a file larger than the cap is reported
  by name and size with the line to continue from. The coder keeps the
  3000-character `TrimmedFileReadTool`.
  Evidence: `swarm/tools_guarded.py`, `swarm/tests/test_verify.py`.
- [x] T3 (AC-4, AC-7): add `build_verify_crew` in `swarm/crew.py` — the
  "Scenario Verifier" agent with `FullFileReadTool` +
  `ShellTool(allow_gates=False, agent_role="verifier")` and **no** write
  tools, so it cannot change the repository; its correction plan is the
  crew's final answer (text), parsed by the harness like the planner's
  `STEP n:` lines and QA's `VERDICT:` line. The prompt asks whether every
  element the brief names exists, whether the pieces connect (the endpoint
  is mounted, the real module is imported, the contract and the code agree)
  and whether the referenced ACs are addressed. Add `verifier_llm()` +
  `SWARM_VERIFIER_MODEL` / `SWARM_VERIFIER_FALLBACK_MODEL` in
  `swarm/llms.py`.
  Evidence: `swarm/crew.py`, `swarm/llms.py`, `.env.example`.
- [x] T4 (AC-5): parse the verifier's answer — `VERDICT: PASS|BLOCKED`, one
  `FINDING:` line per problem, and the correction steps in the planner's own
  `STEP n: <file> — <action>` format (reusing `swarm.crew.STEP_RE`), bounded
  by the planner's `MAX_STEPS`. A blocked verdict without a finding is
  treated as a pass; an ungrounded block ends the round instead of looping.
  Evidence: `swarm/verify.py`, `swarm/tests/test_verify.py`.
- [x] T5 (AC-1, AC-6): run the phase in `swarm/flow.py` — after the
  micro-steps and the 017 self-check, and again after a QA fix round that
  changed the delta: `_verify_phase` builds the context, kicks the verifier,
  and on `BLOCKED` executes the correction steps with `build_step_crew`
  (role `coder:verify<n>`) before verifying again, up to `MAX_VERIFY_ROUNDS`
  (2). `SWARM_VERIFY=0` disables the phase.
  Evidence: `swarm/flow.py::_verify_phase`, `swarm/tests/test_verify.py`.
- [x] T6 (AC-6): a verifier that does not converge ends the run as
  `verifier_blocked` — non-green, `needs_human`, with a copyable reason in
  `human_log.txt` — and never as an unbounded loop.
  Evidence: `swarm/flow.py`, `swarm/humanlog.py`, `swarm/tests/test_verify.py`.
- [x] T7 (AC-8): record every round — `run.json.verifier` holds the verdict,
  the rounds, the findings, the correction plan, the files read and the model;
  `human_log.txt` and the dashboard show the verifier's verdict next to QA's
  (one renderer, so they cannot drift).
  Evidence: `swarm/flow.py::save_run`, `swarm/humanlog.py`, `swarm/tui.py`.
- [x] T8 (AC-9): keep the phase inside the run's budget — rounds, files per
  round, context characters and plan size all bounded, and the verifier's
  usage attributed to its own role (`verifier`) like every other crew.
  Evidence: `swarm/flow.py`, `swarm/tests/test_verify.py`.
- [x] T9: document it — `swarm/README.md` (the phase, the roles, the knobs,
  and how it differs from QA's gates and from the 017 self-check), `AGENTS.md`,
  `docs/roadmap.md`, `changelog.md`; add `019-scenario-verifier` to
  `HARNESS_SPECS`; run `make swarm-test`, `make lint`, `make typecheck`.
  Evidence: `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`, `changelog.md`.

Phase 019 evidence: the 014-T2…T8 runs were all green, and three of them did
not do what their brief said — T2's `GET /geocode` was never mounted in
`app/main.py`, T7's client targets `/api/geocode/suggest` while the pinned
contract says `/geocode`, T8 wired no selection — while T6 and T9 never landed
at all. The gates were green because they test the code that exists; nothing in
the loop ever compared the implementation against the brief. This phase adds
that comparison, with the whole file in view and a correction plan the loop
can execute.
