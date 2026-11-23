#!/bin/sh
# 046 follow-up: one-shot overnight queue run, started by launchd a few minutes
# after the OpenRouter free-tier quota resets (03:00 local).
#
# It is safe to run by hand: `./swarm/night-run.sh` (same behaviour as
# `make swarm-night`, plus the pre-flight the launchd environment lacks).
# `SWARM_NIGHT_DRY=1` checks the environment and exits without starting a run.
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1

# launchd gives a bare environment: add Homebrew (ollama, caffeinate) and the
# usual system paths before anything else.
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export PATH

UID_NUM="$(id -u)"
LABEL="com.comfort.swarm-night"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$REPO/swarm/runs"
LOG="$LOG_DIR/night-$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"

log() { printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" | tee -a "$LOG"; }

log "night-run: starting in $REPO (dry=${SWARM_NIGHT_DRY:-0})"

# NOTE (2026-11-23): do NOT `launchctl bootout` this job up here. Booting out the
# job while it is running terminates this process, which silently stopped the
# wrapper at 03:05 before the supervisor started — nothing ran all night. The
# one-shot retirement now happens *after* the supervisor finishes, below.

# The supervisor never starts the database; gates skip DB tests without
# DATABASE_URL, but e2e and the acceptance pass want it. Best effort only.
if command -v colima >/dev/null 2>&1; then
    eval "$(./swarm/db.sh up 2>/dev/null)" || log "night-run: db.sh up failed (continuing)"
    [ -n "${DATABASE_URL:-}" ] && export DATABASE_URL
fi

# Only start Ollama when a configured role or fallback actually points at it
# (the Go profile does not; a local/free profile does). Starting it anyway just
# burns RAM for the night.
if grep -qE '^\s*SWARM_[A-Z_]*MODEL=ollama/' .env 2>/dev/null; then
    if ! curl -sf --max-time 5 http://localhost:11434/api/tags >/dev/null 2>&1; then
        log "night-run: ollama is configured but down — starting it"
        nohup ollama serve >>"$LOG_DIR/night-ollama.log" 2>&1 &
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            sleep 2
            curl -sf --max-time 3 http://localhost:11434/api/tags >/dev/null 2>&1 && break
        done
    fi
    if curl -sf --max-time 5 http://localhost:11434/api/tags >/dev/null 2>&1; then
        log "night-run: ollama up"
    else
        log "night-run: ollama still down — the fallback chain will fail"
    fi
else
    log "night-run: no ollama model configured — skipping the local server"
fi

# A queue night is long: give it room, but park a task after 3 red attempts so
# one hard task cannot eat the whole night.
SWARM_SUPERVISE_ROUNDS="${SWARM_SUPERVISE_ROUNDS:-60}"
SWARM_SUPERVISE_ATTEMPTS="${SWARM_SUPERVISE_ATTEMPTS:-3}"
export SWARM_SUPERVISE_ROUNDS SWARM_SUPERVISE_ATTEMPTS

if [ "${SWARM_NIGHT_DRY:-0}" = "1" ]; then
    log "night-run: dry run OK (rounds=$SWARM_SUPERVISE_ROUNDS attempts=$SWARM_SUPERVISE_ATTEMPTS)"
    exit 0
fi

log "night-run: starting supervisor (rounds=$SWARM_SUPERVISE_ROUNDS attempts=$SWARM_SUPERVISE_ATTEMPTS)"
# caffeinate: no idle/disk sleep while the queue runs; the run itself may take hours.
caffeinate -is ./swarm/.venv/bin/python -m swarm.supervise >>"$LOG" 2>&1
rc=$?

# One shot: retire the launchd job now that the queue has finished (or stopped).
# This is the safe place for it — the job is no longer running, so bootout does
# not kill anything the run still needs.
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null
rm -f "$PLIST"
exit "$rc"
