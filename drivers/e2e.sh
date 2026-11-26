#!/bin/sh
# The app's e2e driver (056): run the npm suite and report its JSON result.
# Parameters arrive as SWARM_DRIVER_PARAMS ({"specs": [...]}); the suite output
# is passed back in `tail` so the harness's triage keeps working unchanged.
set -u
log=$(mktemp "${TMPDIR:-/tmp}/swarm-e2e.XXXXXX")
specs=$(python3 -c 'import json,os; print(" ".join(json.loads(os.environ.get("SWARM_DRIVER_PARAMS") or "{}").get("specs") or []))')
# shellcheck disable=SC2086 # specs are repo paths without spaces
npm --prefix frontend run test:e2e $specs >"$log" 2>&1
code=$?
python3 - "$log" "$code" <<'PY'
import json, pathlib, sys
tail = pathlib.Path(sys.argv[1]).read_text(errors="replace")[-8000:]
print(json.dumps({"exit": int(sys.argv[2]), "detail": "npm test:e2e", "tail": tail}))
PY
rm -f "$log"
exit "$code"
