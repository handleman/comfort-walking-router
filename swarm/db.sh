#!/bin/sh
# Local Postgres for the saved-routes feature (005), driven by `make swarm-db-*`.
# Colima is part of the swarm lifecycle: `make swarm-run`/`swarm-up` start it
# (best-effort) and `make swarm-stop`/`swarm-db-down` stop it.
#
#   ./swarm/db.sh up       start colima + the container, wait, migrate, print the
#                          export (chatter on stderr; `export DATABASE_URL=…` on
#                          stdout so a recipe can `eval "$(./swarm/db.sh up)"`)
#   ./swarm/db.sh down [--all]  stop the container; --all also stops colima
#   ./swarm/db.sh status   one line: up <version> / down
#   ./swarm/db.sh env      `DATABASE_URL=…` when the container is up (Makefile prefix)
#   ./swarm/db.sh migrate  upgrade the schema to head
#
# The app reads DATABASE_URL from the environment at import (`app/db.py`), it
# does not load `.env`; that is why this prints an `export` line instead of
# writing a file. Values are overridable: SWARM_DB_URL, SWARM_DB_CONTAINER,
# SWARM_DB_IMAGE. Missing colima is a no-op, not an error: DB-gated tests skip.
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

CONTAINER=${SWARM_DB_CONTAINER:-comfort-pg}
IMAGE=${SWARM_DB_IMAGE:-postgres:16-alpine}
URL=${SWARM_DB_URL:-postgresql://postgres:comfort@localhost:5432/comfort}
PY="$REPO_ROOT/.venv/bin/python"

running() {
    docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true
}

exists() {
    docker inspect "$CONTAINER" >/dev/null 2>&1
}

wait_ready() {
    i=0
    while [ "$i" -lt 60 ]; do
        if docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
            return 0
        fi
        i=$((i + 1))
        sleep 1
    done
    return 1
}

migrate() {
    DATABASE_URL=$URL "$PY" -c "from app import db; db.run_migrations(); print('schema at head')"
}

start() {
    # Bring colima + the container up, migrate, and print the export. Chatter
    # goes to stderr so `eval "$(./swarm/db.sh up)"` sets only DATABASE_URL.
    if ! command -v colima >/dev/null 2>&1; then
        echo "colima not installed — local Postgres skipped (DB-gated tests will skip)" >&2
        return 0
    fi
    if ! colima status >/dev/null 2>&1; then
        echo "starting colima (4 CPU / 8 GB / 60 GB)…" >&2
        colima start --cpu 4 --memory 8 --disk 60 >/dev/null
    fi
    if exists; then
        running || { echo "starting ${CONTAINER}…" >&2; docker start "$CONTAINER" >/dev/null; }
    else
        echo "creating $CONTAINER from $IMAGE…" >&2
        # The account exists for public images; a missing credsStore otherwise
        # fails every pull (2026-11-15).
        docker run -d --name "$CONTAINER" \
            -e POSTGRES_PASSWORD=comfort -e POSTGRES_DB=comfort \
            -p 5432:5432 "$IMAGE" >/dev/null
    fi
    if ! wait_ready; then
        echo "postgres did not become ready in 60s" >&2
        return 1
    fi
    migrate >&2
    echo "export DATABASE_URL=$URL"
}

case "${1:-}" in
up)
    start
    ;;
down)
    running && { echo "stopping ${CONTAINER}…"; docker stop "$CONTAINER" >/dev/null; }
    if [ "${2:-}" = "--all" ]; then
        colima stop >/dev/null 2>&1 || true
        echo "colima stopped"
    fi
    ;;
status)
    if running; then
        version=$(docker exec "$CONTAINER" psql -U postgres -d comfort -tAc "select version()" 2>/dev/null | cut -d, -f1)
        echo "up — ${version:-running}"
    else
        echo "down (make swarm-db-up)"
    fi
    ;;
env)
    running && echo "DATABASE_URL=$URL"
    ;;
migrate)
    migrate
    ;;
*)
    echo "usage: $0 {up|down [--all]|status|env|migrate}" >&2
    exit 2
    ;;
esac
