# 017 Coder Self-Check — Plan

## Approach

A new harness phase between "the micro-steps are done" and "QA reviews the
work". It mirrors the existing style-repair phase (016) but one level up: the
style phase repairs *mechanical* failures, the self-check *detects* the failures
that only the coder can fix and hands them over with the evidence.

### Where it sits

```
plan → steps (coder) → SELF-CHECK (harness) → coder fix round(s) → QA → gates → verdict
```

The self-check runs the static subset of `SWARM_GATE_COMMANDS`: the type checker
and the linter, never the test suites. In this repo that is
`ruff check .`, `mypy app tests`, `npm --prefix frontend run check` and
`npm --prefix frontend run lint` — about four seconds.

### Why the harness runs it and not the coder

015 D1 made QA the only gate executor, and that stays. The self-check is run by
the harness (not by an agent) under its own agent role, so:

- its records are never counted as QA evidence (`gate_evidence` filters by
  agent role) — the phase can never make a run green;
- the coder still cannot run a gate, so a coder cannot certify its own work;
- the report reaches the coder in the same shape as QA's report (failing first,
  `file:line: message` key lines), which the coder already knows how to read.

### Formatting stays with the harness

A Prettier/ESLint wrap is mechanical. Before the report is built, the harness
runs the project's formatter (`SWARM_STYLE_FIX_COMMAND`) when the only red
static check is style-only, and re-checks. The coder never sees a wrap as a
"code problem" — the same rule the QA path already applies.

### Configuration

| Variable | Meaning |
| --- | --- |
| `SWARM_SELF_CHECK` | `0` disables the phase (default on) |
| `SWARM_SELF_CHECK_COMMANDS` | explicit commands; empty = derive from the gates |

The derivation is a heuristic over the command line (`ruff`, `mypy`, `pyright`,
`tsc`, `eslint`, `prettier`, `svelte-check`, npm scripts `check`/`lint`/
`typecheck`, make targets `check`/`lint`/`typecheck`). It is only a default:
the project can always name its own commands.

## Steps

1. `swarm/selfcheck.py` — command classification, configuration, report
   rendering (`file:line: message` key lines, failing first, bounded).
2. `swarm/crew.py` — `build_selfcheck_crew()`: a coder-only crew (no gates)
   whose prompt carries the report and the type-error discipline already in
   `FIX_RULES`.
3. `swarm/flow.py` — `_run_self_check()` (run + record), `_self_check_phase()`
   (bounded fix rounds), `_apply_formatter()` extracted from `_autofix_style()`
   so the formatter is shared by both paths.
4. `swarm/style.py` — `style_failures()`: the failing commands whose output
   names nothing but formatting (the QA path keeps the stricter
   "sole failure" rule).
5. `swarm/tui.py` — the dashboard shows a red self-check under "why".
6. Tests: `swarm/tests/test_selfcheck.py`.

## Risks / Open Questions

- **Cost:** the phase adds ~4 s per dev attempt and, when red, one coder round.
  A coder round on the local model is free; on a paid model it is the price of
  not losing three QA rounds.
- **False positives:** the checks run after *all* micro-steps, so the code is
  expected to be internally consistent; running them between steps would
  report errors for work that later steps complete.
- **Duplicated work:** the static checks run twice (self-check, then QA). That
  is the price of early feedback; the QA copy is the one that counts.

## Verification

- `make swarm-test` (harness tests, incl. `swarm/tests/test_selfcheck.py`)
- `make lint`, `make typecheck`, `make test`
- `npm --prefix frontend run check`, `run lint`, `test -- --run`
- Manual: a deliberate type error in `frontend/src/` must show up in the
  self-check report with `file:line: message` before QA is invoked.
