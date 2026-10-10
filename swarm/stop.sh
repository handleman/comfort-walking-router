#!/bin/sh
# Stop the currently running pilot (if any): ./swarm/stop.sh
# Kills `python -m swarm.flow` only; Ollama and dashboards are untouched.
if ! pgrep -f "swarm\.flow" > /dev/null; then
  echo "no pilot running"
  exit 0
fi
pkill -f "swarm\.flow"
sleep 3
if pgrep -f "swarm\.flow" > /dev/null; then
  pkill -9 -f "swarm\.flow"
  sleep 2
fi
if pgrep -f "swarm\.flow" > /dev/null; then
  echo "failed to stop pilot (still running)"
  exit 1
fi
echo "pilot stopped"
