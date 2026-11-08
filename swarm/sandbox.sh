#!/usr/bin/env bash
# Run the pilot in a container sandbox (012 T17).
#
# Isolation: the only bind mount is the repo ($PWD:/work). No HOME, SSH agent,
# shell history, or host caches. Capabilities are dropped, PID/memory are
# capped, and the process runs as the host UID so committed files stay yours.
#
# Network is still required (OpenRouter/Zen/Ollama). Ollama on the host is
# reached via host.docker.internal; bind it on 0.0.0.0 for Docker to see it:
#   OLLAMA_HOST=0.0.0.0 ollama serve
#
# Commits: sandbox runs default to --no-commit because the container has no
# git credentials. Review the diff on the host and commit there, or opt in:
#   SWARM_SANDBOX_ALLOW_COMMIT=1 SWARM_SANDBOX_SSH=1 ./swarm/sandbox.sh ...
#
# Usage: ./swarm/sandbox.sh [--dry-run] [spec] [task] [flow flags]
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"
IMAGE="${SWARM_SANDBOX_IMAGE:-swarm-sandbox}"

if [ "${1:-}" = "--dry-run" ]; then
  shift
  DRY=1
else
  DRY=0
fi

ALLOW_COMMIT="${SWARM_SANDBOX_ALLOW_COMMIT:-0}"
ORIG_ARGS=("$@")
if [ "$ALLOW_COMMIT" != "1" ]; then
  set -- "$@" --no-commit
fi
if [ ${#ORIG_ARGS[@]} -eq 0 ]; then
  set -- --resume "$@"
fi

OLLAMA_IN="${SWARM_SANDBOX_OLLAMA_URL:-http://host.docker.internal:11434}"
GIT_NAME="$(git config user.name 2>/dev/null || echo swarm)"
GIT_EMAIL="$(git config user.email 2>/dev/null || echo swarm@localhost)"

print_cmd() {
  local out="" a
  for a in "$@"; do out+="$(printf '%q ' "$a")"; done
  printf '%s\n' "${out% }"
}

COMMON=(
  --rm -i
  --name "swarm-sandbox-$$"
  --user "$(id -u):$(id -g)"
  --cap-drop=ALL
  --security-opt=no-new-privileges
  --pids-limit=512
  --memory=8g
  --add-host=host.docker.internal:host-gateway
  -v "$REPO:/work"
  -w /work
  -e OLLAMA_BASE_URL="$OLLAMA_IN"
  -e HOME=/tmp
  -e PYTHONPATH=/work
  -e GIT_CONFIG_COUNT=1
  -e GIT_CONFIG_KEY_0=safe.directory
  -e GIT_CONFIG_VALUE_0=/work
  -e GIT_AUTHOR_NAME="$GIT_NAME"
  -e GIT_AUTHOR_EMAIL="$GIT_EMAIL"
  -e GIT_COMMITTER_NAME="$GIT_NAME"
  -e GIT_COMMITTER_EMAIL="$GIT_EMAIL"
)
if [ -f "$REPO/.env" ]; then
  # Pass values as env, but mask the file inside the mount so the coder
  # process/tools cannot read secrets from the repo.
  COMMON=("${COMMON[@]}" --env-file "$REPO/.env" -v /dev/null:/work/.env:ro)
fi
if [ -f "$REPO/swarm/.env" ]; then
  COMMON=("${COMMON[@]}" -v /dev/null:/work/swarm/.env:ro)
fi
if [ "${SWARM_SANDBOX_SSH:-0}" = "1" ]; then
  COMMON=("${COMMON[@]}" -v "$HOME/.ssh:/tmp/.ssh:ro" -e GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new")
fi

if [ "$DRY" = "1" ]; then
  echo "docker build -t $IMAGE -f swarm/docker/Dockerfile ."
  print_cmd docker run "${COMMON[@]}" "$IMAGE" "$@"
  echo "# mounts: $REPO -> /work (only)" >&2
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for the sandbox (see swarm/README.md)" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not running (start Docker Desktop, or: colima start --cpu 4 --memory 8)" >&2
  exit 1
fi
if [ "$ALLOW_COMMIT" = "1" ] && [ "${SWARM_SANDBOX_SSH:-0}" != "1" ]; then
  echo "warning: commits enabled without an SSH mount — HTTPS remotes need a token" >&2
fi

if [ "${SWARM_SANDBOX_NO_BUILD:-0}" != "1" ]; then
  docker build -t "$IMAGE" -f swarm/docker/Dockerfile . >&2
fi
exec docker run "${COMMON[@]}" "$IMAGE" "$@"
