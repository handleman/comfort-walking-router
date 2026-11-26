# Local Postgres runbook

The local database backs the saved-routes feature (spec 005): saved routes and
the `default_preference` live behind `app/db.py`, a handful of app tests and the
three `preferences` e2e scenarios need it, and the swarm's `make` targets export
`DATABASE_URL` to it automatically when it is up.

## Commands

```bash
make swarm-db-up        # start colima + comfort-pg, migrate, print DATABASE_URL
make swarm-db-status    # one line: up <version> / down
make swarm-db-migrate   # upgrade the schema to head
make swarm-db-down      # stop comfort-pg + colima + the running pilot
```

`make swarm-db-up` then `make test` runs the DB-gated tests against it (the app
tests skip them when the database is down). Colima is part of the swarm
lifecycle: `make swarm-run`/`swarm-up` start it best-effort before the pilot,
and `make swarm-stop` stops it.

## How DATABASE_URL reaches the app

The app reads `DATABASE_URL` from `os.environ` at import (`app/db.py`), not from
`.env`. The Makefile exports it: `DB_ENV := $(shell ./harness/db.sh env)` prefixes
`make test|e2e|swarm-run|swarm-bench-live|smoke-live` with `DATABASE_URL=…` when
the container is running. `app/env.py` loads the repo `.env` at import (for
`MAPBOX_TOKEN` and friends); python-dotenv never overrides an existing export,
so the Makefile's value wins.

## Limits

Without the database (`make swarm-db-down`): the 005 saved-routes app tests and
the three `preferences` e2e specs skip, the saved-routes endpoints answer 5xx,
and the schema must be at head (`make swarm-db-migrate`) before those paths work
again.

Ran while writing: `make swarm-db-status` (up — PostgreSQL 16.16) and `make test`
(214 passed).
