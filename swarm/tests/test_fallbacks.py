import pytest

from swarm import llms


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    # The operator `.env` is loaded by `swarm.flow`, so a cloud-only profile would
    # otherwise leak into these default-chain tests. Clear the fallback knobs so
    # each test sees the code defaults unless it sets them itself.
    for var in (
        "SWARM_PLANNER_FALLBACK_MODEL",
        "SWARM_CODER_FALLBACK_MODEL",
        "SWARM_REVIEWER_FALLBACK_MODEL",
        "SWARM_SENIOR_FALLBACK_MODEL",
        "SWARM_VERIFIER_FALLBACK_MODEL",
        "SWARM_LOCAL_FALLBACK_MODEL",
        "SWARM_ALLOW_PAID",
    ):
        monkeypatch.delenv(var, raising=False)
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
    # First fallback is paid Zen; the local fallback is the safe default behind it.
    assert llms.fallback_model("SWARM_SENIOR_MODEL", allow_paid=False) == "ollama/swarm-coder:latest"


def test_zen_fallback_used_when_paid_allowed(monkeypatch):
    monkeypatch.setenv("SWARM_ALLOW_PAID", "1")
    assert llms.fallback_model("SWARM_SENIOR_MODEL", allow_paid=True) == "zen/glm-5.3-flash"


def test_env_fallback_has_precedence(monkeypatch):
    monkeypatch.setenv("SWARM_ALLOW_PAID", "1")
    monkeypatch.setenv("SWARM_SENIOR_FALLBACK_MODEL", "zen/deepseek-v4.1-flash")
    assert llms.fallback_model("SWARM_SENIOR_MODEL", allow_paid=True) == "zen/deepseek-v4.1-flash"


def test_role_fallback_moves_only_that_role(monkeypatch):
    """007-T4: a coder timeout degraded QA to a 9B model that could not review."""
    monkeypatch.setenv("SWARM_CODER_MODEL", "ollama/swarm-coder:latest")
    monkeypatch.setenv("SWARM_REVIEWER_MODEL", "ollama/swarm-qa:latest")
    llms.activate_fallbacks("SWARM_CODER_MODEL")
    assert llms.fallbacks_active("SWARM_CODER_MODEL") is True
    assert llms.fallbacks_active("SWARM_REVIEWER_MODEL") is False
    assert llms.coder_llm().model == "ollama/swarm-coder:latest"  # no-op: same model
    assert llms.reviewer_llm().model == "ollama/swarm-qa:latest"


def test_coder_fallback_prefers_the_local_coder(monkeypatch):
    monkeypatch.setenv("SWARM_ALLOW_PAID", "1")
    assert (
        llms.fallback_model("SWARM_CODER_MODEL", allow_paid=True)
        == "ollama/swarm-coder:latest"
    )


def test_local_fallback_is_configurable_and_shared(monkeypatch):
    """One knob: every role falls back to the configured local model."""
    monkeypatch.setenv("SWARM_LOCAL_FALLBACK_MODEL", "ollama/qwen3.5:9b")
    for env_var in (
        "SWARM_PLANNER_MODEL",
        "SWARM_CODER_MODEL",
        "SWARM_REVIEWER_MODEL",
    ):
        assert llms.fallback_model(env_var, allow_paid=False) == "ollama/qwen3.5:9b"
    assert llms.default_fallback_chain("SWARM_SENIOR_MODEL")[1] == "ollama/qwen3.5:9b"


def test_local_fallback_defaults_to_the_coder_model(monkeypatch):
    monkeypatch.delenv("SWARM_LOCAL_FALLBACK_MODEL", raising=False)
    assert llms.local_fallback_model() == "ollama/swarm-coder:latest"


def test_global_activation_covers_every_role(monkeypatch):
    monkeypatch.setenv("SWARM_CODER_MODEL", "ollama/swarm-coder:latest")
    assert llms.fallbacks_active() is False
    llms.activate_fallbacks()
    assert llms.fallbacks_active("SWARM_CODER_MODEL") is True
    assert llms.fallbacks_active("SWARM_REVIEWER_MODEL") is True


def test_role_models_reflect_the_active_fallback(monkeypatch):
    """The dashboard must show the model actually called, per role."""
    monkeypatch.setenv("SWARM_ALLOW_PAID", "1")
    monkeypatch.setenv("SWARM_CODER_MODEL", "zen/glm-5.3-flash")
    monkeypatch.setenv("SWARM_REVIEWER_MODEL", "ollama/swarm-qa:latest")
    llms.activate_fallbacks("SWARM_CODER_MODEL")
    rows = {m["role"]: m for m in llms.role_models()}
    assert rows["coder"]["model"] == "ollama/swarm-coder:latest"
    assert rows["coder"]["fallback"] is True
    assert rows["reviewer"]["model"] == "ollama/swarm-qa:latest"
    assert rows["reviewer"]["fallback"] is False
    assert llms.fallback_roles() == ["SWARM_CODER_MODEL"]


def test_verdict_fallback_is_the_senior_model(monkeypatch):
    """A missing local verdict is decided by the senior brain, not a second id."""
    monkeypatch.setenv("SWARM_SENIOR_MODEL", "openrouter/nvidia/x:free")
    monkeypatch.setenv("SWARM_ALLOW_PAID", "0")
    assert llms.verdict_fallback_llm().model == "nvidia/x:free"


def test_verdict_fallback_never_uses_a_paid_model(monkeypatch):
    monkeypatch.setenv("SWARM_SENIOR_MODEL", "zen/glm-5.3-flash")
    monkeypatch.setenv("SWARM_ALLOW_PAID", "0")
    with pytest.raises(PermissionError):
        llms.verdict_fallback_llm()
