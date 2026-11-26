# Comfort walking router — top-level shortcuts.
# App: make dev (bootstraps deps on first run). Swarm: make swarm-*.

.PHONY: dev dev-setup dev-setup-python dev-backend dev-frontend test lint typecheck e2e \
	swarm-run swarm-dash swarm-up swarm-test swarm-local swarm-up-local \
	swarm-stop swarm-approve swarm-preflight provider-audit \
	swarm-supervise swarm-report swarm-log swarm-night swarm-record \
	swarm-bench swarm-bench-build swarm-bench-baseline swarm-bench-live swarm-parallel \
	swarm-replay swarm-replay-off swarm-replay-one swarm-replay-paid \
	swarm-db-up swarm-db-down swarm-db-status swarm-db-migrate smoke-live

PYTHON ?= $(shell command -v python3.12 || command -v python3)
VENV ?= .venv
PY := $(VENV)/bin/python
# 005: when the local Postgres is up, every target that needs it gets
# DATABASE_URL automatically (the app reads os.environ, not .env).
SWARM_DB_URL ?= postgresql://postgres:comfort@localhost:5432/comfort
DB_ENV := $(shell ./harness/db.sh env 2>/dev/null)

dev: ## Start backend :8000 + frontend :5173; Ctrl-C stops both
	@test -x "$(PY)" || $(MAKE) --no-print-directory dev-setup-python
	@test -d frontend/node_modules || { echo "Installing frontend dependencies..."; cd frontend && npm install; }
	@echo "Backend:  http://localhost:8000/docs"
	@echo "Frontend: http://localhost:5173"
	@set -e; \
		$(PY) -m uvicorn app.main:app --reload --port 8000 & backend=$$!; \
		(cd frontend && ./node_modules/.bin/vite --port 5173 --strictPort) & frontend=$$!; \
		trap 'kill $$backend $$frontend 2>/dev/null || true' INT TERM EXIT; \
		wait

dev-setup: dev-setup-python ## Install Python + frontend dependencies
	cd frontend && npm install

dev-setup-python: ## Create .venv and install Python dependencies
	@echo "Creating $(VENV) and installing Python dependencies..."
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt -r requirements-dev.txt

dev-backend: ## Backend only (http://localhost:8000/docs)
	@test -x "$(PY)" || { echo "Missing $(VENV); run: make dev-setup"; exit 1; }
	$(PY) -m uvicorn app.main:app --reload --port 8000

dev-frontend: ## Frontend only (http://localhost:5173; proxies /route to :8000)
	@test -d frontend/node_modules || { echo "Missing frontend deps; run: make dev-setup"; exit 1; }
	cd frontend && npm run dev -- --port 5173 --strictPort

test: ## App tests (pytest)
	$(DB_ENV) $(PY) -m pytest -q

lint: ## Ruff lint (app + swarm)
	$(PY) -m ruff check .

typecheck: ## Mypy typecheck (app + tests)
	$(PY) -m mypy app tests

swarm-run: ## Pilot run (starts colima+Postgres if needed): make swarm-run [SPEC=001] [TASK=T1]
	@eval "$$(./harness/db.sh up)"; ./harness/run.sh $(SPEC) $(TASK)

swarm-accept: ## Spec acceptance pass (final greenlight; all product specs)
	harness/.venv/bin/python -m swarm.drivers.acceptance $(ARGS)

swarm-local: ## All-local pilot (Ollama Qwen for all roles, ignores cloud .env): make swarm-local [SPEC=001] [TASK=T1]
	@eval "$$(./harness/db.sh up)"; SWARM_PLANNER_MODEL=ollama/qwen3.5:9b SWARM_REVIEWER_MODEL=ollama/qwen3.5:9b ./harness/run.sh $(SPEC) $(TASK)

swarm-up-local: ## All-local pilot in background + dashboard attached
	@eval "$$(./harness/db.sh up)"; SWARM_PLANNER_MODEL=ollama/qwen3.5:9b SWARM_REVIEWER_MODEL=ollama/qwen3.5:9b ./harness/up.sh $(SPEC) $(TASK)

swarm-dash: ## Dashboard attached to current pilot
	./harness/dash.sh

swarm-up: ## Pilot in background + dashboard attached: make swarm-up [SPEC=001] [TASK=T1]
	@eval "$$(./harness/db.sh up)"; ./harness/up.sh $(SPEC) $(TASK)

swarm-supervise: ## Unattended queue: auto-resume retryable stops, park exhausted tasks
	harness/.venv/bin/python -m swarm.supervise

swarm-report: ## Cost/autonomy report from harness/runs (cost per green task, roles, stops)
	harness/.venv/bin/python -m swarm.report

swarm-log: ## Human-readable "why did this stop?" report [RUN=<run dir>] (default: newest)
	harness/.venv/bin/python -m swarm.humanlog $(RUN)

swarm-night: ## Overnight run: keep the Mac awake (caffeinate) + auto-resume the queue
	@echo "overnight: caffeinate -is + supervisor; keep the machine on AC power"
	caffeinate -is harness/.venv/bin/python -m swarm.supervise

swarm-parallel: ## Race independent tasks in worktrees, integrate greens serially: BATCH="spec:task,..." WORKERS=2
	@test -n "$(BATCH)" || { echo 'BATCH="spec:task,spec:task" is required'; exit 2; }
	harness/.venv/bin/python -m swarm.parallel --batch "$(BATCH)" --workers $${WORKERS:-2}

swarm-bench: ## Offline replay bench vs baseline.json (020): prompt/report chars, no model call
	harness/.venv/bin/python -m swarm.drivers.bench $(ARGS)

swarm-bench-build: ## Rebuild the frozen replay corpus from green runs (git history)
	harness/.venv/bin/python -m swarm.drivers.bench --build

swarm-bench-baseline: ## Snapshot the current bench score as baseline.json (before a harness change)
	harness/.venv/bin/python -m swarm.drivers.bench --update-baseline

swarm-replay-paid: ## Replay suite with the agreed paid coder + fast QA and a base-compatible formatter
	SWARM_BENCH_MODELS="coder=zen/glm-5.3-flash,qa=openrouter/nvidia/nemotron-3.5-lightning:free" \
	SWARM_STYLE_FIX_COMMAND="npm --prefix frontend run format" \
	harness/.venv/bin/python -m swarm.drivers.bench.replay $(ARGS)

swarm-replay: ## Outcome replay suite (5–8 cases, models required; compares to replay_baseline.json)
	harness/.venv/bin/python -m swarm.drivers.bench.replay $(ARGS)

swarm-replay-off: ## Same suite with every 021 knob at its 020 value (A/B side)
	harness/.venv/bin/python -m swarm.drivers.bench.replay --off

swarm-replay-one: ## One case with details: make swarm-replay-one CASE=<id>
	@test -n "$(CASE)" || { echo "CASE=<corpus id> is required"; exit 2; }
	harness/.venv/bin/python -m swarm.drivers.bench.replay --case $(CASE) --json

swarm-bench-live: ## Live replay of one case in a throwaway worktree: make swarm-bench-live CASE=<id>
	@test -n "$(CASE)" || { echo "CASE=<corpus id> is required (see: make swarm-bench ARGS=--list)"; exit 2; }
	$(DB_ENV) harness/.venv/bin/python -m swarm.drivers.bench --live $(CASE)

swarm-test: ## Harness install check (version + preflight; the factory owns its unit tests)
	harness/.venv/bin/hq --version
	harness/.venv/bin/python -m swarm.preflight

e2e: ## Browser e2e suite (fixture backend + vite preview + playwright test)
	$(DB_ENV) harness/.venv/bin/python -m swarm.drivers.e2e

swarm-record: ## Record a manually completed task's trailers: make swarm-record SPEC=001 TASK=T3
	@test -n "$(SPEC)" -a -n "$(TASK)" || { echo "SPEC=<spec dir> TASK=<T3> are required"; exit 2; }
	harness/.venv/bin/python -m swarm.record $(SPEC) $(TASK)

# swarm-coder-image: built by the factory image (handleman-hq).


# swarm-qa-image: built by the factory image (handleman-hq).


swarm-stop: ## Stop the running pilot and colima (Postgres included)
	./harness/stop.sh; ./harness/db.sh down --all

swarm-db-up: ## Start colima + local Postgres, migrate, print the DATABASE_URL export
	./harness/db.sh up

swarm-db-down: ## Stop the local Postgres + colima and the running pilot
	./harness/db.sh down --all; ./harness/stop.sh

swarm-db-status: ## Is the local Postgres up?
	./harness/db.sh status

swarm-db-migrate: ## Upgrade the local Postgres schema to head
	./harness/db.sh migrate

smoke-live: ## Real providers (no fixtures): one Munich route, profile and weather
	$(DB_ENV) harness/.venv/bin/python -m swarm.drivers.smoke

corridor-check: ## Live Overpass corridor probe (three mirrors; non-zero if none serve)
	harness/.venv/bin/python -m swarm.drivers.corridor_check

swarm-health: ## Run the app + e2e suites; non-zero if the test stand is broken
	harness/.venv/bin/python -m swarm.drivers.health

provider-audit: ## Key-free reachability probe across every supported provider
	harness/.venv/bin/python -m swarm.provider_audit

swarm-preflight: ## Validate models/keys/Ollama/venvs/gates before a run
	harness/.venv/bin/python -m swarm.preflight

npm-lock-check: ## Verify frontend/package-lock.json is in sync with package.json
	cd frontend && npm ci --dry-run

# The container sandbox lives in the factory image (handleman-hq).


swarm-approve: ## Approve a held task: make swarm-approve [SPEC=001] [TASK=T3] (default: last checkpoint)
	./harness/run.sh $(if $(SPEC),--spec $(SPEC),) $(if $(TASK),--task $(TASK),) --approve
