# 018 Operator-Readable Runs — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [x] T1 (AC-1): add `swarm/humanlog.py` — a dependency-free renderer that
  names the stop reason, the reason code, the failing gates, the reviewer's
  verdict and the changed files; `write_human_report(run_dir)` writes
  `<run_dir>/human_log.txt`.
  Evidence: `swarm/humanlog.py`, `swarm/tests/test_humanlog.py`.
- [x] T2 (AC-1): every run writes the report — `save_run` calls
  `write_human_report` right after `run.json` (suppressed: it must never fail
  a run). Evidence: `swarm/flow.py::save_run`.
- [x] T3 (AC-2): the dashboard screen and the written file are the same
  renderer — `swarm/tui.py::format_human_report` delegates to
  `swarm.humanlog`; `HumanLogScreen` gains a `c` binding that copies the
  report to the clipboard.
  Evidence: `swarm/tui.py`, `swarm/tests/test_humanlog.py::test_dashboard_screen_and_file_render_the_same_text`.
- [x] T4 (AC-3): `make swarm-log [RUN]` prints the report for a run (default:
  the newest) without a TUI. Evidence: `swarm/humanlog.py::main`,
  `Makefile`.
- [x] T5 (AC-4): the budget panel states that the token and cost caps do not
  apply to a free-local run instead of showing a percentage of a cap that
  cannot fire. Evidence: `swarm/tui.py::format_metrics`,
  `swarm/tests/test_tui_format.py`.
- [x] T6 (AC-5): a truncated file read names the exact line to continue from
  (`CONTINUE with start_line=<n>`), so a re-read makes progress instead of
  repeating the same head of the file.
  Evidence: `swarm/tools_guarded.py::TrimmedFileReadTool`,
  `swarm/tests/test_trimmed_read.py`.
- [x] T7 (AC-6): the reviewer gets enough iterations to declare a verdict
  after running every gate (`max_iter` 9 → 12), and the verdict repair runs
  on a red run too, so `review_verdict` is never silently "unknown" when a
  gate failed. Evidence: `swarm/crew.py::_reviewer`,
  `swarm/flow.py::_maybe_repair_verdict`,
  `swarm/tests/test_autoloop.py`.
- [x] T8: pin spec 014's geocoding contract so one shape exists —
  `plan.md` fixes the `Suggestion` fields, the token variable
  (`MAPBOX_TOKEN`), the Mapbox v6 and Photon wire formats and the
  contract↔dataclass mapping; `contracts/geocode.json`, `app/geocoding.py`
  and `tests/test_geocoding.py` are rewritten to match.
  Evidence: `specs/014-walk-guidance-ux/plan.md`, `contracts/geocode.json`,
  `app/geocoding.py`, `tests/test_geocoding.py` (12 fixture-only tests).

Phase 018 evidence (2026-11-12): the 014-T1 run
(`swarm/runs/20261112-004043-1092-2c1c`) spent 50 minutes and 229 calls on a
one-line defect. The operator could not copy the reason out of the dashboard,
the budget panel showed a token cap that was never enforced, the fixer
re-read the same 85 lines of a 178-line file seven times, and the reviewer
never declared a verdict. All four are fixed here, and spec 014's geocoding
contract is pinned so the next run has one target.
