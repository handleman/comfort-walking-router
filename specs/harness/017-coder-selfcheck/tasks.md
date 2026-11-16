# 017 Coder Self-Check — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [x] T1 (AC-1, AC-2): add `swarm/selfcheck.py` — classify the static checks
  (`SWARM_SELF_CHECK_COMMANDS` or the static subset of `SWARM_GATE_COMMANDS`,
  `SWARM_SELF_CHECK=0` disables) and render a bounded report with the failing
  command, its exit code and `file:line: message` key lines.
  Evidence: `swarm/selfcheck.py`, `swarm/tests/test_selfcheck.py`.
- [x] T2 (AC-3): run the self-check between the micro-steps and QA; a red check
  gives the coder a fix round (`build_selfcheck_crew`, coder only, no gates)
  and the checks are re-run, bounded by `MAX_SELF_CHECK_ROUNDS`.
  Evidence: `swarm/flow.py::_self_check_phase`, `swarm/crew.py`.
- [x] T3 (AC-4): the self-check runs under its own agent role
  (`harness-selfcheck`), so its records are never QA evidence and the phase can
  never make a run green. Evidence: `swarm/tests/test_selfcheck.py::test_self_check_never_counts_as_qa_evidence`.
- [x] T4 (AC-5): the commands are configuration, not a harness assumption.
  Evidence: `swarm/selfcheck.py::commands`, `swarm/tests/test_selfcheck.py`.
- [x] T5 (AC-6): a formatting-only failure is still repaired by the harness
  (formatter + re-check) before the report is built, so a wrap never reaches
  the coder as a code problem. Evidence: `swarm/style.py::style_failures`,
  `swarm/flow.py::_apply_formatter`.
- [x] T6 (AC-7): `run.json.self_check` records the commands, their exit codes,
  the red ones and the number of fix rounds; the dashboard shows a red
  self-check under "why". Evidence: `swarm/flow.py::save_run`, `swarm/tui.py`.

Phase 017 evidence (2026-11-12): the 007-T9 run (2026-11-11) spent three QA
rounds and two coder rounds on `Property 'tick' does not exist on type
'PositionProvider'` — an error the checker had already named. The harness now
runs the static checks itself right after the micro-steps and hands the report
to the coder, so the defect is fixed before QA is ever asked to review.
