#!/bin/sh
# Dashboard attached to the current pilot: ./swarm/dash.sh
# Follows swarm/runs/latest (events.jsonl + run.json), live, even mid-run.
# Falls back to the newest run dir when the pointer is missing (older runs).
cd "$(dirname "$0")/.." || exit 1
LATEST="$(cat swarm/runs/latest 2>/dev/null)"
if [ -z "$LATEST" ] || [ ! -d "swarm/runs/$LATEST" ]; then
  LATEST="$(ls -1 swarm/runs 2>/dev/null | grep -E '^[0-9]{8}-[0-9]{6}$' | sort | tail -n 1)"
fi
if [ -z "$LATEST" ] || [ ! -d "swarm/runs/$LATEST" ]; then
  echo "no pilot run yet. Start one: ./swarm/run.sh (or make swarm-up)"
  exit 1
fi
exec swarm/.venv/bin/python -m swarm.tui --tail "swarm/runs/$LATEST"
