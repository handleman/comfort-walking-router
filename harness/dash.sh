#!/bin/sh
# Dashboard attached to the current pilot: ./harness/dash.sh
# Follows harness/runs/latest (events.jsonl + run.json), live, even mid-run.
# Falls back to the newest run dir when the pointer is missing (older runs).
cd "$(dirname "$0")/.." || exit 1
LATEST="$(cat harness/runs/latest 2>/dev/null)"
if [ -z "$LATEST" ] || [ ! -d "harness/runs/$LATEST" ]; then
  LATEST="$(ls -1 harness/runs 2>/dev/null | grep -E '^[0-9]{8}-[0-9]{6}' | sort | tail -n 1)"
fi
if [ -z "$LATEST" ] || [ ! -d "harness/runs/$LATEST" ]; then
  echo "no pilot run yet. Start one: ./harness/run.sh (or make swarm-up)"
  exit 1
fi
exec harness/.venv/bin/python -m swarm.tui --tail "harness/runs/$LATEST"
