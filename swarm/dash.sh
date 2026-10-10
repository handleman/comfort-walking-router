#!/bin/sh
# Dashboard attached to the current pilot: ./swarm/dash.sh
# Follows swarm/runs/latest (events.jsonl + run.json), live, even mid-run.
cd "$(dirname "$0")/.." || exit 1
LATEST="$(cat swarm/runs/latest 2>/dev/null)"
if [ -z "$LATEST" ] || [ ! -d "swarm/runs/$LATEST" ]; then
  echo "no pilot run yet (swarm/runs/latest missing). Start one: ./swarm/run.sh"
  exit 1
fi
exec swarm/.venv/bin/python -m swarm.tui --tail "swarm/runs/$LATEST"
