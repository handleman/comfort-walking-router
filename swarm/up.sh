#!/bin/sh
# Combined: start pilot in background, open dashboard attached to it.
# Usage: ./swarm/up.sh [spec-prefix] [task]
cd "$(dirname "$0")/.." || exit 1
BEFORE="$(cat swarm/runs/latest 2>/dev/null)"
./swarm/run.sh "$@" > swarm/runs/up.log 2>&1 &
i=0
while [ $i -lt 40 ]; do
  LATEST="$(cat swarm/runs/latest 2>/dev/null)"
  if [ -n "$LATEST" ] && [ "$LATEST" != "$BEFORE" ] && [ -d "swarm/runs/$LATEST" ]; then
    break
  fi
  sleep 1; i=$((i + 1))
done
if [ -z "$LATEST" ] || [ ! -d "swarm/runs/$LATEST" ]; then
  echo "pilot failed to start; see swarm/runs/up.log"
  exit 1
fi
exec ./swarm/dash.sh
