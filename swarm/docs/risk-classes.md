# Risk classes and the escape rate (024)

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

The swarm is **autonomous by default**: a green run merges. There is no switch
to turn autonomy on and no risk ceiling to configure — a run whose gates all
exit `0`, whose reviewer says `VERDICT: PASS` and whose scenario verifier is not
blocked goes through the branch, the `--no-ff` merge queue, the trailers and the
push by itself.

What remains is *measurement*: every run carries a risk label, and
`make swarm-report` turns later reverts into an escape rate per label. The label
is telemetry, never a gate.

## Classes

| Class | Paths | What |
| --- | --- | --- |
| 0 docs | `docs/**`, `*.md` | prose and ADRs |
| 1 tests | `tests/**`, `frontend/e2e/**` | tests and browser specs |
| 2 logic | `app/**`, `frontend/src/**`, `contracts/**` | behaviour a user feels |
| 3 control | `swarm/**`, `specs/**`, migrations, auth/payments/infra, config, unknown, empty delta | the harness, the specs, the process |

`swarm/risk.py::classify` is conservative by construction: an empty or
unrecognised delta is 3, and a brief mentioning auth/payment/migration/infra/
secret is 3 whatever the paths. The label lands in `run.json.risk`
(`class`, `label`) even when the run is not green, so a stopped run still says
what kind of change it was attempting.

## The one hold left: `--require-approval`

`./swarm/run.sh 007 T10 --require-approval` holds a green run at
`awaiting_approval` for a look before the commit (dashboard `a`, or
`make swarm-approve`; the held delta is committed through the normal merge
queue, so the approval path is the same evidence). It is a per-run flag for a
deliberate review, not a mode: nothing in `.env` makes the swarm stop merging by
itself. `--no-commit` skips the commit path entirely for a dry experiment.

## The default autonomous loop

A green run autocommits **only the run-delta in-scope changes** and pushes, then
loops back to the planner for the next task — and after a spec's last task, to
the next spec with tasks (directory order; specs without `tasks.md` and the
harness specs are skipped). The first non-green task stops the whole loop
(`needs_human`/`crew_error`/`commit_failed`/`push_failed`/`merge_failed`/
`quota_exhausted`/`budget_exhausted`/`interrupted`/`preflight_failed` in that
task's `run.json`). Flags: `--single` runs only the given task, `--no-commit`
skips autocommit+push (passed through `run.sh`, e.g.
`./swarm/run.sh 001 T1 --single`).

## Escape rate

`make swarm-report` joins every merged (green) run with git: it looks up the
task's commit by its `Swarm-Task:` trailer and counts an escape when a later
commit says `This reverts commit <sha>`. The line reads
`escapes: E/M (P%) — class 2 E/M, …`, per class.

A hand-fixed regression is not a detected escape, so the ratio is a **floor**.
It is the only honest measure of whether the autonomous path is safe, and the
reason the class is recorded even though nothing gates on it.
