#!/bin/sh
# Stop the currently running pilot (if any): ./swarm/stop.sh
# Prefers the harness PID file; falls back to matching `python -m swarm.flow`.
# Ollama and dashboards are untouched.
PIDFILE=swarm/runs/swarm.pid
if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE" 2>/dev/null)"
  if [ -n "$PID" ] && kill "$PID" 2>/dev/null; then
    sleep 3
    if kill -0 "$PID" 2>/dev/null; then
      kill -9 "$PID" 2>/dev/null
      sleep 2
    fi
    if kill -0 "$PID" 2>/dev/null; then
      echo "failed to stop pilot pid $PID (still running)"
      exit 1
    fi
    rm -f "$PIDFILE"
    echo "pilot stopped (pid $PID)"
    exit 0
  fi
fi
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
