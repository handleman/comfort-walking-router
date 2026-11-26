#!/bin/sh
# Swarm pilot run: ./harness/run.sh [spec-prefix] [task]  (no args = resume from last checkpoint)
# Extra args pass through to swarm.flow. Run dir recorded in harness/runs/latest.
cd "$(dirname "$0")/.." || exit 1
case "${1:-}" in
  -*)
    # Flag-first invocation (e.g. `./harness/run.sh --approve`): pass through as-is.
    exec harness/.venv/bin/python -m swarm.flow "$@"
    ;;
esac
if [ $# -eq 0 ] || { [ $# -eq 2 ] && [ -z "$1" ] && [ -z "$2" ]; }; then
  shift $#
  exec harness/.venv/bin/python -m swarm.flow --resume "$@"
fi
SPEC="${1:-001}"; TASK="${2:-T1}"
if [ $# -ge 2 ]; then shift 2; else shift $#; fi
exec harness/.venv/bin/python -m swarm.flow --spec "$SPEC" --task "$TASK" "$@"
