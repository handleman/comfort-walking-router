# 018 Operator-Readable Runs — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

The 014-T1 run (`swarm/runs/20261112-004043-1092-2c1c`) ended `needs_human`
after 50 minutes, 229 LLM calls and three fix rounds, with a defect that was
one wrong string in one line:

```
tests/test_geocoding.py:39: AssertionError: assert '123 Main St' == '123 Main Street'
```

Three separate things went wrong, and none of them was the code:

1. **The answer was not pasteable.** The dashboard shows a "why did this stop?"
   screen (`h`), but a terminal screen cannot be copied, piped or attached to
   an issue. The report existed only inside the TUI.
2. **The budget panel lied.** It showed "tokens 1.7M / 2.0M 84.0%" for a run
   whose dollar/token caps are *not enforced* (`free_local_run: true`), so the
   operator reasonably concluded the budget had stopped the run. It had not —
   the run stopped on a failed assertion.
3. **The fixer never saw the file it had to fix.** The read tool truncates
   observations at 3000 characters and said only "re-read with
   start_line/line_count". The coder asked for lines 1–500 of a 178-line file
   **seven times** and got the same first 85 lines every time; it never saw
   `search()` at line 169. It spent its rounds re-reading, changed nothing,
   and the run ended `no_progress`.

Two smaller defects compounded them: the reviewer ran out of iterations
before declaring a verdict (`review_verdict: "unknown"`, so the fix rounds
had no grounded reason), and the verdict repair only ran when the gates were
*green* — a red run, which is exactly when a verdict is needed most.

## Goal

A stopped run must explain itself in a form the operator can take away, and
the harness must not waste rounds on a defect the agent cannot see.

## Acceptance criteria

- **AC-1** — Every run writes a plain-text human-readable report next to its
  `run.json` (`<run_dir>/human_log.txt`) naming the stop reason, the reason
  code, the failing gates, the reviewer's verdict and the changed files.
- **AC-2** — The dashboard's human-log screen and the written report are the
  same renderer, so they cannot drift; the screen can copy the report to the
  clipboard (`c`).
- **AC-3** — `make swarm-log [RUN]` prints the report for a run (default: the
  newest) without a TUI, so it can be piped (`| pbcopy`).
- **AC-4** — The budget panel states that the token and cost caps do not
  apply to a free-local run, instead of showing a percentage of a cap that
  cannot fire.
- **AC-5** — A truncated file read names the exact line to continue from, so
  a re-read makes progress instead of repeating the same head of the file.
- **AC-6** — The reviewer gets enough iterations to declare a verdict after
  running every gate, and the verdict repair runs on a red run too, so
  `review_verdict` is never silently "unknown" when a gate failed.

## Non-goals

- The report is a plain-text view of the existing `run.json` / `events.jsonl`;
  it introduces no new state and no new contract.
- The report is not a substitute for the dashboard's live view: it is the
  take-away copy.
- Nothing here decides *what* the geocoding contract is (that is spec 014's
  plan.md, which was pinned in the same change).
