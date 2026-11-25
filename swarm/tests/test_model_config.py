"""047: one source of truth — router, free predicate, roles, Profile (golden)."""

from __future__ import annotations

from swarm import model_config


def test_provider_routes_every_prefix_and_unknown():
    assert model_config.provider("ollama/swarm-coder:latest") == "ollama"
    assert model_config.provider("zen/glm-5.3-flash") == "zen"
    assert model_config.provider("opencode-go/glm-5.3-flash") == "opencode-go"
    assert model_config.provider("openrouter/nvidia/x:free") == "openrouter"
    assert model_config.provider("") == "unknown"
    assert model_config.provider("?") == "unknown"
    # A bare id routes to OpenRouter (the default gateway).
    assert model_config.provider("anthropic/claude") == "openrouter"


def test_is_free_covers_local_and_free_tiers_only():
    assert model_config.is_free("ollama/swarm-coder:latest") is True
    assert model_config.is_free("openrouter/nvidia/x:free") is True
    assert model_config.is_free("opencode-go/hy4-flash-free") is True
    assert model_config.is_free("openrouter/foo-contributor-free") is True
    assert model_config.is_free("opencode-go/glm-5.3-flash") is False


def test_the_one_free_predicate_agrees_everywhere():
    """AC-2: usage, llms._guard and preflight all call the same function."""
    from swarm import llms, preflight, usage

    for model in (
        "ollama/swarm-coder:latest",
        "openrouter/nvidia/x:free",
        "opencode-go/hy4-flash-free",
        "opencode-go/glm-5.3-flash",
        "anthropic/claude-sonnet-4",
    ):
        expected = model_config.is_free(model)
        assert usage.is_free(model) is expected
        assert preflight.is_free_model(model) is expected

    # `_guard` refuses exactly the paid set when the operator has not opted in.
    import os

    previous = os.environ.get("SWARM_ALLOW_PAID")
    os.environ["SWARM_ALLOW_PAID"] = "0"
    try:
        llms._guard("openrouter/nvidia/x:free")  # allowed
        try:
            llms._guard("anthropic/claude-sonnet-4")
        except PermissionError:
            pass
        else:
            raise AssertionError("a paid id must be refused")
    finally:
        if previous is None:
            os.environ.pop("SWARM_ALLOW_PAID", None)
        else:
            os.environ["SWARM_ALLOW_PAID"] = previous


def test_the_router_agrees_everywhere():
    """AC-3: llms and preflight route through the same table."""
    from swarm import llms, preflight

    for model in (
        "ollama/x:latest",
        "zen/glm-5.3-flash",
        "opencode-go/glm-5.3-flash",
        "openrouter/nvidia/x:free",
        "",
    ):
        assert llms.provider_of(model) == model_config.provider(model)
        assert preflight.provider(model) == model_config.provider(model)


def test_roles_are_one_table_with_the_expected_shape():
    names = [r.name for r in model_config.ROLES]
    assert names == ["planner", "coder", "reviewer", "senior", "verifier"]
    optional = [r.name for r in model_config.ROLES if r.optional]
    assert optional == ["verifier"]
    # The legacy tuples still have the same values (no consumer churn).
    assert model_config.ROLE_MODEL_VARS[0] == ("planner", "SWARM_PLANNER_MODEL")
    assert "SWARM_SENIOR_MODEL" in model_config.ROLE_VARS
    assert "SWARM_VERIFIER_MODEL" in model_config.OPTIONAL_ROLE_VARS
    assert "SWARM_VERIFIER_MODEL" not in model_config.ROLE_VARS


def test_resolve_inherits_senior_for_the_verifier_and_local_fallback():
    env = {
        "SWARM_CODER_MODEL": "opencode-go/glm-5.3-flash",
        "SWARM_CODER_FALLBACK_MODEL": "opencode-go/mimo-v2.6-flash",
        "SWARM_SENIOR_MODEL": "opencode-go/deepseek-v4-pro",
        "SWARM_LOCAL_FALLBACK_MODEL": "ollama/swarm-coder:latest",
        "SWARM_ALLOW_PAID": "1",
    }
    profile = model_config.resolve_models(env)
    assert profile.primary("coder") == "opencode-go/glm-5.3-flash"
    assert profile.fallback("coder") == "opencode-go/mimo-v2.6-flash"
    # The verifier has no id of its own: it uses the senior brain.
    assert profile.primary("verifier") == "opencode-go/deepseek-v4-pro"
    # Any role without an explicit fallback uses the shared local fallback.
    assert profile.fallback("planner") == "ollama/swarm-coder:latest"
    assert profile.role("coder").free is False
    assert profile.paid_allowed is True
