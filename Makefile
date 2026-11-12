# Comfort walking router — top-level shortcuts.
# App: make dev (bootstraps deps on first run). Swarm: make swarm-*.

.PHONY: dev dev-setup dev-setup-python dev-backend dev-frontend test lint typecheck \
	swarm-run swarm-dash swarm-up swarm-test swarm-local swarm-up-local \
	swarm-coder-image swarm-qa-image swarm-stop swarm-approve swarm-preflight swarm-sandbox \
	swarm-supervise swarm-report swarm-log swarm-night

PYTHON ?= $(shell command -v python3.12 || command -v python3)
VENV ?= .venv
PY := $(VENV)/bin/python

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
	$(PY) -m pytest -q

lint: ## Ruff lint (app + swarm)
	$(PY) -m ruff check .

typecheck: ## Mypy typecheck (app + tests)
	$(PY) -m mypy app tests

swarm-run: ## Pilot run: make swarm-run [SPEC=001] [TASK=T1]
	./swarm/run.sh $(SPEC) $(TASK)

swarm-local: ## All-local pilot (Ollama Qwen for all roles, ignores cloud .env): make swarm-local [SPEC=001] [TASK=T1]
	SWARM_PLANNER_MODEL=ollama/qwen3.5:9b SWARM_REVIEWER_MODEL=ollama/qwen3.5:9b ./swarm/run.sh $(SPEC) $(TASK)

swarm-up-local: ## All-local pilot in background + dashboard attached
	SWARM_PLANNER_MODEL=ollama/qwen3.5:9b SWARM_REVIEWER_MODEL=ollama/qwen3.5:9b ./swarm/up.sh $(SPEC) $(TASK)

swarm-dash: ## Dashboard attached to current pilot
	./swarm/dash.sh

swarm-up: ## Pilot in background + dashboard attached: make swarm-up [SPEC=001] [TASK=T1]
	./swarm/up.sh $(SPEC) $(TASK)

swarm-supervise: ## Unattended queue: auto-resume retryable stops, park exhausted tasks
	swarm/.venv/bin/python -m swarm.supervise

swarm-report: ## Cost/autonomy report from swarm/runs (cost per green task, roles, stops)
	swarm/.venv/bin/python -m swarm.report

swarm-log: ## Human-readable "why did this stop?" report [RUN=<run dir>] (default: newest)
	swarm/.venv/bin/python -m swarm.humanlog $(RUN)

swarm-night: ## Overnight run: keep the Mac awake (caffeinate) + auto-resume the queue
	@echo "overnight: caffeinate -is + supervisor; keep the machine on AC power"
	caffeinate -is swarm/.venv/bin/python -m swarm.supervise

swarm-test: ## Harness unit tests (no LLM, no network)
	swarm/.venv/bin/python -m pytest swarm/tests -q

swarm-coder-image: ## Build tuned local coder image (swarm/ollama/Modelfile -> swarm-coder:latest)
	ollama create swarm-coder -f swarm/ollama/Modelfile

swarm-qa-image: ## Build tuned local QA image (swarm/ollama/Modelfile.qa -> swarm-qa:latest)
	ollama create swarm-qa -f swarm/ollama/Modelfile.qa

swarm-stop: ## Stop the currently running pilot (Ollama/dashboards untouched)
	./swarm/stop.sh

swarm-preflight: ## Validate models/keys/Ollama/venvs/gates before a run
	swarm/.venv/bin/python -m swarm.preflight

swarm-sandbox: ## Run the pilot in the container sandbox (repo is the only mount)
	./swarm/sandbox.sh

swarm-approve: ## Approve a held task: make swarm-approve [SPEC=001] [TASK=T3] (default: last checkpoint)
	./swarm/run.sh $(if $(SPEC),--spec $(SPEC),) $(if $(TASK),--task $(TASK),) --approve
