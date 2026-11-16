# 030 Operator Runbooks — Spec

Harness/operator spec (the queue never runs it — these pages document the
swarm's own operation, so the operator writes them by hand). Four independent,
one-file-each tasks; the four pages and the README section can be written in any
order.

## Problem

The operator surface grew faster than its documentation. Four things a new
operator (or a future session) needs are scattered across commits, this file and
`AGENTS.md`:

1. the local Postgres that `make swarm-db-*` starts, what it is for, and how to
   stop it;
2. the browser suite: `make e2e`, fixtures mode, the `preferences` specs and why
   they need a database;
3. what verification actually proves — the gate list, the profile smoke, and
   which claims are *not* verified (replay convergence, escape rate);
4. the environment variables that are easy to get wrong (`MAPBOX_TOKEN`,
   `DATABASE_URL`, `OPENCODE_GO_API_KEY`) and where they must live.

Each answer exists in code or a changelog entry, and each is one `docs/runbooks/`
page (or a README section) away from being usable.

## Goal

Four pages under `docs/runbooks/` plus one README section, each naming the exact
commands it documents, each verified by running them, and each explicitly stating
what it does not cover. One task per file so the parallel factory can run them
concurrently.

## Scope

- `docs/runbooks/local-postgres.md` — `make swarm-db-up|down|status|migrate`,
  what `DATABASE_URL` is used for (005 routes/prefs, the DB-gated tests, the
  `preferences` e2e), what happens without it (tests skip, prefs specs skip), and
  how to stop colima.
- `docs/runbooks/e2e-suite.md` — `make e2e`, fixtures mode (`ROUTE_FIXTURES=1`),
  the fixture backend and `vite preview`, why the suite is evidence for 026, and
  the three `preferences` specs' database dependency.
- `docs/runbooks/verification.md` — what `make test`, `make lint`,
  `make typecheck`, `make swarm-test`, `make e2e`, `make smoke-live` and
  `make swarm-preflight` each prove, and what none of them prove (replay
  convergence 1/5, escape rate 0/12 with no window, real-GPS human gate).
- `README.md` — a "Verification" section linking those three pages and the
  harness docs, with the one-line commands.

## Non-goals

- Rewriting `AGENTS.md` or `swarm/docs/` (the harness docs are separate and
  already split by topic).
- Documenting the swarm's internal phases (that is `swarm/docs/how-it-works.md`).
- Any code change.

## Acceptance criteria

- **AC-1 — Commands are real.** Every command in every page exists in the
  `Makefile` (or is a documented shell command), and the page names the target it
  uses. A command that was renamed must be updated in the same task.
- **AC-2 — Limits are stated.** Each page has a short "what this does not prove"
  (or "limits") section: a page that only says what works is not useful.
- **AC-3 — One file per task.** T1–T3 touch exactly one `docs/runbooks/*.md`
  file each, T4 touches only `README.md`, so the four tasks have disjoint deltas
  and can run in parallel.
- **AC-4 — Verified while writing.** Each task runs the commands it documents
  (or records that a dependency such as Postgres or a token is required) and says
  which were run.

## Success definition

A new operator can go from a fresh checkout to a running app, a green suite and an
honest idea of what is verified, without reading the changelog.
