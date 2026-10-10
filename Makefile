# Comfort walking router — top-level shortcuts.
# App targets land with 001-T1 (pytest/ruff/mypy/npm). Swarm targets work now.

.PHONY: swarm-run swarm-dash swarm-up swarm-test swarm-local swarm-up-local swarm-coder-image swarm-stop

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

swarm-test: ## Harness unit tests (no LLM, no network)
	swarm/.venv/bin/python -m pytest swarm/tests -q

swarm-coder-image: ## Build tuned local coder image (swarm/ollama/Modelfile -> swarm-coder:latest)
	ollama create swarm-coder -f swarm/ollama/Modelfile

swarm-stop: ## Stop the currently running pilot (Ollama/dashboards untouched)
	./swarm/stop.sh
