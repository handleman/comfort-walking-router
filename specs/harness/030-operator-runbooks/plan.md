# 030 Operator Runbooks — Plan

## Shape

Four files, four tasks, zero code:

| Task | File | Content |
| --- | --- | --- |
| T1 | `docs/runbooks/local-postgres.md` | `make swarm-db-*`, `DATABASE_URL`, what needs it, how to stop |
| T2 | `docs/runbooks/e2e-suite.md` | `make e2e`, fixtures mode, the prefs/DB dependency, 026 evidence |
| T3 | `docs/runbooks/verification.md` | each target's claim, and the unverified list |
| T4 | `README.md` (Verification section) | the one-screen index into the three pages |

Disjoint files are the point: `make swarm-parallel BATCH="030:T1,030:T2,030:T3,030:T4"`
can run all four at once, and the measurement (wall clock vs the serial sum) is
023's missing number.

## Page skeleton (T1–T3)

```
# <title>
What it is · Commands (a fenced block, each command real) · What needs it
Limits — what this does not prove / what breaks without it
```

Rules for the writer:

- name the `make` target, not a paraphrased shell incantation;
- state the fallback (tests skip, prefs specs skip, weather-only score) where a
  dependency is missing;
- no invented flags: read the `Makefile` target and `swarm/db.sh` usage first;
- keep each page under ~80 lines; links go to `swarm/docs/` for harness detail.

## README section (T4)

```md
## Verification
| Command | Proves |
| --- | --- |
| `make test` | app behaviour, including the DB-backed repositories when Postgres is up |
| `make e2e` | the user scenarios in a browser (fixtures backend) |
| `make smoke-live` | one real route through real providers (tokens required) |
| `make swarm-test` | the harness itself, no model calls |
| `make lint` / `make typecheck` | style and types |
```

Followed by three links (`docs/runbooks/local-postgres.md`, `e2e-suite.md`,
`verification.md`) and one sentence pointing at `swarm/docs/` for the harness.

## Measurement

After the four greens: record wall clock for the parallel batch next to the sum
of the serial cases in `changelog.md` (023 AC: throughput is a measurement, not a
claim). The expectation is a 2–3× speedup on four ~2–4 minute tasks with
`SWARM_WORKERS=4`; anything less is a finding to write down, not to round up.
