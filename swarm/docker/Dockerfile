# Sandbox image for the swarm pilot (012 T17).
# Build from the repo root: docker build -f swarm/docker/Dockerfile -t swarm-sandbox .
# The container gets exactly one mount (`$PWD:/work`) at runtime; no HOME, SSH,
# or host caches are mounted unless explicitly opted in.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/work

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git nodejs npm openssh-client \
    && rm -rf /var/lib/apt/lists/*

# App + harness dependencies, and the server-side gates (pytest/ruff/mypy).
# Keep the harness deps in sync with swarm/pyproject.toml.
COPY requirements.txt requirements-dev.txt /tmp/
RUN pip install -r /tmp/requirements.txt -r /tmp/requirements-dev.txt \
    && pip install "crewai[litellm]" crewai-tools textual python-dotenv rich

# Run as an unprivileged user; sandbox.sh passes --user $(id -u):$(id -g) so
# files written into /work keep the host owner.
RUN useradd --create-home --uid 1000 swarm
USER swarm

WORKDIR /work
ENTRYPOINT ["python", "-m", "swarm.flow"]
