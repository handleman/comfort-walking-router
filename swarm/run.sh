#!/bin/sh
# Swarm pilot run: ./swarm/run.sh [spec-prefix] [task]  (defaults: 001 T1)
# Extra args pass through to swarm.flow. Run dir recorded in swarm/runs/latest.
cd "$(dirname "$0")/.." || exit 1
SPEC="${1:-001}"; TASK="${2:-T1}"
if [ $# -ge 2 ]; then shift 2; else shift $#; fi
exec swarm/.venv/bin/python -m swarm.flow --spec "$SPEC" --task "$TASK" "$@"
