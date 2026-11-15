#!/bin/sh
# Local Postgres for the saved-routes feature (005), driven by `make swarm-db-*`.
#
#   ./swarm/db.sh up       start colima + the container, wait, migrate, print the export
#   ./swarm/db.sh down     stop the container (colima keeps running)
#   ./swarm/db.sh down --all   stop the container and colima
#   ./swarm/db.sh status   one line: up <version> / down
#   ./swarm/db.sh env      `DATABASE_URL=…` when the container is up (Makefile prefix)
#   ./swarm/db.sh migrate  upgrade the schema to head
#
# The app reads DATABASE_URL from the environment at import (`app/db.py`), it
# does not load `.env`; that is why this prints an `export` line instead of
# writing a file. Values are overridable: SWARM_DB_URL, SWARM_DB_CONTAINER,
# SWARM_DB_IMAGE.
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

case "${1:-}" in
up)
    if ! colima status >/dev/null 2>&1; then
        echo "starting colima (4 CPU / 8 GB / 60 GB)…"
        colima start --cpu 4 --memory 8 --disk 60 >/dev/null
    fi
    if exists; then
        running || { echo "starting $CONTAINER…"; docker start "$CONTAINER" >/dev/null; }
    else
        echo "creating $CONTAINER from $IMAGE…"
        # The account exists for public images; a missing credsStore otherwise
        # fails every pull (2026-11-15).
        docker run -d --name "$CONTAINER" \
            -e POSTGRES_PASSWORD=comfort -e POSTGRES_DB=comfort \
            -p 5432:5432 "$IMAGE" >/dev/null
    fi
    wait_ready || { echo "postgres did not become ready in 60s" >&2; exit 1; }
    migrate
    echo "export DATABASE_URL=$URL"
    ;;
down)
    running && { echo "stopping $CONTAINER…"; docker stop "$CONTAINER" >/dev/null; }
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
