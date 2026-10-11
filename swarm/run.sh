#!/bin/sh
# Swarm pilot run: ./swarm/run.sh [spec-prefix] [task]  (no args = resume from last checkpoint)
# Extra args pass through to swarm.flow. Run dir recorded in swarm/runs/latest.
cd "$(dirname "$0")/.." || exit 1
if [ $# -eq 0 ] || { [ $# -eq 2 ] && [ -z "$1" ] && [ -z "$2" ]; }; then
  exec swarm/.venv/bin/python -m swarm.flow --resume
fi
SPEC="${1:-001}"; TASK="${2:-T1}"
if [ $# -ge 2 ]; then shift 2; else shift $#; fi
exec swarm/.venv/bin/python -m swarm.flow --spec "$SPEC" --task "$TASK" "$@"
