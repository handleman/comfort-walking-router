# 018 Operator-Readable Runs — Plan

## Approach

Four independent changes, one new module.

### 1. `swarm/humanlog.py` (new) — the report renderer

Dependency-free (no textual, no crewai) so the harness can write it headlessly.

- `format_human_report(payload, events, *, run_name, event_limit)` — the
  renderer, moved out of `swarm/tui.py`. Same text as the dashboard screen
  before, plus the `reason_code` line (the one field that names the stop
  reason in machine-readable form).
- `write_human_report(run_dir)` — writes `<run_dir>/human_log.txt`.
- `latest_run_dir()`, `main()` — the CLI behind `make swarm-log`.

`swarm/tui.py` keeps `format_human_report` as a thin delegation, so the
dashboard and the file can never disagree (test asserts equality).

### 2. `swarm/flow.py` — write the report at the end of every run

`save_run` writes `run.json`; immediately after, `write_human_report` writes
the report. Wrapped in `contextlib.suppress(Exception)`: the report is a
convenience and must never fail a run.

### 3. `swarm/tui.py` — truthful budget + copyable report

- `format_metrics` reads `budget.free_local_run` from the payload. For a
  free-local run it prints `tokens 1.7M (no cap: free local run)` instead of
  a percentage of `SWARM_MAX_TOKENS` — a cap `_check_budget` never applies.
- `HumanLogScreen` gains a `c` binding that copies the report via Textual's
  `copy_to_clipboard`.

### 4. `swarm/tools_guarded.py` + `swarm/crew.py` + `swarm/flow.py` — the
   wasted rounds

- `TrimmedFileReadTool` counts the lines it actually returned and appends
  `CONTINUE with start_line=<n> (do not re-read from line <start>)`. The
  014-T1 coder re-read lines 1–500 seven times because the old note did not
  say where the file had been cut.
- `_reviewer().max_iter` 9 → 12: six gates + `git status` + the verdict + a
  look at the failing file is ~9 calls, so a budget of 9 left the reviewer
  re-running `pytest` instead of declaring a verdict.
- `_maybe_repair_verdict` no longer requires green gates. The repair used to
  run only when the gates were green; a red run is exactly when a verdict
  matters, and it is what tells the coder which gate is failing.

### 5. Spec 014 — pin the geocoding contract

The T1 defect was not a typo. Three shapes for `Suggestion` existed at once:
`plan.md` said `{id, label, lat, lng, type, attribution}`, the (green)
`contracts/geocode.json` said `{label, coordinates{lat,lng}, attribution,
feature_type}`, and the coder wrote `{label, lat, lng, provider, attribution}`
against a Mapbox **v5** payload (`formatted`/`center`) where the plan said
**v6** (`full_address`/`coordinates`). The token variable was a third
mismatch: `MAPBOX_TOKEN` in the plan, `MAPBOX_ACCESS_TOKEN` in the code (a
variable that exists nowhere in the repo).

`plan.md` now pins: the `Suggestion` shape, the token variable, the two
provider wire formats, and that the contract mirrors `Suggestion` field for
field. `contracts/geocode.json` and `app/geocoding.py` + `tests/test_geocoding.py`
were rewritten to match.

## Risks / open questions (resolved choices)

- **Report size.** The report embeds the reviewer output and the gate
  transcript (2.5k each) plus the last 80 events. It is a paste target, not
  an archive: `run.json` remains the contract.
- **Two renderers?** No: `swarm/tui.py` delegates to `swarm/humanlog.py`, and
  a test asserts the screen and the file render identically.
- **Does the free-local exemption really skip the token cap?** Yes:
  `_check_budget` passes `max_tokens=0` when `local` is true, so
  `budget_note` never trips on tokens. The old panel showed that never-trips
  cap as a percentage.
- **Reopening the verdict repair on red runs:** the repair may answer BLOCKED
  where the reviewer would have said PASS. That is safe — a red gate can
  never be green, and `gate()` re-checks every gate's exit code.

## Files

- `swarm/humanlog.py` (new), `swarm/tui.py`, `swarm/flow.py`,
  `swarm/tools_guarded.py`, `swarm/crew.py`, `Makefile`.
- `swarm/tests/test_humanlog.py` (new), `swarm/tests/test_trimmed_read.py`,
  `swarm/tests/test_tui_format.py`, `swarm/tests/test_autoloop.py`.
- `specs/018-operator-readable-runs/{spec,plan,tasks}.md`.
- `specs/014-walk-guidance-ux/{plan,tasks}.md`, `contracts/geocode.json`,
  `app/geocoding.py`, `tests/test_geocoding.py`.
