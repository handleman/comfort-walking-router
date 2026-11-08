import pytest

from swarm import llms


@pytest.fixture(autouse=True)
def _reset():
    llms.reset_fallbacks()
    yield
    llms.reset_fallbacks()


def test_inactive_fallbacks_keep_primary(monkeypatch):
    monkeypatch.setenv("SWARM_PLANNER_MODEL", "openrouter/nvidia/x:free")
    monkeypatch.setenv("SWARM_PLANNER_FALLBACK_MODEL", "ollama/qwen3.5:9b")
    assert llms.planner_llm().model == "nvidia/x:free"


def test_activated_fallback_uses_env_override(monkeypatch):
    monkeypatch.setenv("SWARM_PLANNER_MODEL", "openrouter/nvidia/x:free")
    monkeypatch.setenv("SWARM_PLANNER_FALLBACK_MODEL", "ollama/qwen3.5:9b")
    llms.activate_fallbacks()
    llm = llms.planner_llm()
    assert llm.model == "ollama/qwen3.5:9b"
    assert llm.is_litellm is True


def test_paid_fallback_skipped_without_allow_paid(monkeypatch):
    monkeypatch.setenv("SWARM_ALLOW_PAID", "0")
    monkeypatch.setenv("SWARM_SENIOR_MODEL", "openrouter/nvidia/x:free")
    # First fallback is paid Zen; local Qwen is the safe default behind it.
    assert llms.fallback_model("SWARM_SENIOR_MODEL", allow_paid=False) == "ollama/qwen3.5:9b"


def test_zen_fallback_used_when_paid_allowed(monkeypatch):
    monkeypatch.setenv("SWARM_ALLOW_PAID", "1")
    assert llms.fallback_model("SWARM_SENIOR_MODEL", allow_paid=True) == "zen/glm-5.3-flash"


def test_env_fallback_has_precedence(monkeypatch):
    monkeypatch.setenv("SWARM_ALLOW_PAID", "1")
    monkeypatch.setenv("SWARM_SENIOR_FALLBACK_MODEL", "zen/deepseek-v4.1-flash")
    assert llms.fallback_model("SWARM_SENIOR_MODEL", allow_paid=True) == "zen/deepseek-v4.1-flash"


def test_fallback_activation_is_process_wide(monkeypatch):
    monkeypatch.setenv("SWARM_CODER_MODEL", "ollama/swarm-coder:latest")
    assert llms.fallbacks_active() is False
    llms.activate_fallbacks()
    assert llms.fallbacks_active() is True
    assert llms.coder_llm().model == "ollama/qwen3.5:9b"
