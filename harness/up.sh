#!/bin/sh
# Combined: start pilot in background, open dashboard attached to it.
# Usage: ./harness/up.sh [spec-prefix] [task]
cd "$(dirname "$0")/.." || exit 1
BEFORE="$(cat harness/runs/latest 2>/dev/null)"
./harness/run.sh "$@" > harness/runs/up.log 2>&1 &
i=0
while [ $i -lt 40 ]; do
  LATEST="$(cat harness/runs/latest 2>/dev/null)"
  if [ -n "$LATEST" ] && [ "$LATEST" != "$BEFORE" ] && [ -d "harness/runs/$LATEST" ]; then
    break
  fi
  sleep 1; i=$((i + 1))
done
if [ -z "$LATEST" ] || [ ! -d "harness/runs/$LATEST" ]; then
  echo "pilot failed to start; see harness/runs/up.log"
  exit 1
fi
exec ./harness/dash.sh
