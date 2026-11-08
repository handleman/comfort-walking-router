"""Test defaults: clean checkouts have no `.env`, so provide non-secret placeholder models.

Real `.env` values (when present) always win; this only fills the gaps so tests
that build CrewAI LLM objects do not depend on a developer machine's keys.
"""

import os

import pytest

_MODEL_DEFAULTS = {
    "SWARM_PLANNER_MODEL": "ollama/qwen3.5:9b",
    "SWARM_CODER_MODEL": "ollama/swarm-coder:latest",
    "SWARM_REVIEWER_MODEL": "ollama/swarm-qa:latest",
    "SWARM_SENIOR_MODEL": "ollama/qwen3.5:9b",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "SWARM_ALLOW_PAID": "0",
}
_KEY_DEFAULTS = {
    "OPENROUTER_API_KEY": "test-openrouter-key",
    "OPENCODE_API_KEY": "test-opencode-key",
}


@pytest.fixture(autouse=True)
def _default_swarm_env(monkeypatch):
    for key, value in {**_MODEL_DEFAULTS, **_KEY_DEFAULTS}.items():
        if not os.environ.get(key):
            monkeypatch.setenv(key, value)
