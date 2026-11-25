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


# ---- 047 AC-4: the crew timeout is a profile property -----------------------


def test_the_crew_timeout_follows_the_profile():
    cloud = model_config.resolve_models(
        {"SWARM_CODER_MODEL": "opencode-go/glm-5.3-flash"}
    )
    assert not cloud.local
    assert cloud.crew_timeout() == 300.0

    local = model_config.resolve_models({"SWARM_CODER_MODEL": "ollama/swarm-coder:latest"})
    assert local.local
    assert local.crew_timeout() == 900.0


def test_each_profile_has_its_own_timeout_knob():
    cloud = model_config.resolve_models(
        {
            "SWARM_CODER_MODEL": "opencode-go/glm-5.3-flash",
            "SWARM_CREW_TIMEOUT_SECONDS": "42",
            "SWARM_LOCAL_CREW_TIMEOUT_SECONDS": "7",
        }
    )
    assert cloud.crew_timeout() == 42.0
    local = model_config.resolve_models(
        {
            "SWARM_CODER_MODEL": "ollama/swarm-coder:latest",
            "SWARM_CREW_TIMEOUT_SECONDS": "42",
            "SWARM_LOCAL_CREW_TIMEOUT_SECONDS": "7",
        }
    )
    assert local.crew_timeout() == 7.0


def test_llms_delegates_the_timeout_to_the_profile():
    from swarm import llms

    assert llms.crew_timeout_seconds(
        {"SWARM_CODER_MODEL": "ollama/swarm-coder:latest"}
    ) == 900.0
    assert llms.crew_timeout_seconds(
        {"SWARM_CODER_MODEL": "opencode-go/glm-5.3-flash"}
    ) == 300.0


# ---- 047 AC-3: the router a role reports is the one it calls ----------------


def test_the_flow_role_provider_reads_the_profile(monkeypatch):
    from swarm import flow

    monkeypatch.setenv("SWARM_CODER_MODEL", "opencode-go/glm-5.3-flash")
    assert flow._role_provider("coder:step1") == "opencode-go"
    monkeypatch.setenv("SWARM_REVIEWER_MODEL", "ollama/swarm-qa:latest")
    assert flow._role_provider("qa") == "ollama"


# ---- 047 AC-6: fallbacks are validated like primaries ----------------------


def test_preflight_flags_a_paid_fallback_without_allow_paid():
    from swarm import preflight

    env = {
        "SWARM_PLANNER_MODEL": "opencode-go/glm-5.3-flash",
        "SWARM_CODER_MODEL": "opencode-go/glm-5.3-flash",
        "SWARM_REVIEWER_MODEL": "opencode-go/qwen3.8-flash",
        "SWARM_SENIOR_MODEL": "opencode-go/deepseek-v4-pro",
        "SWARM_PLANNER_FALLBACK_MODEL": "opencode-go/mimo-v2.6-flash",
        "SWARM_ALLOW_PAID": "0",
        "OPENCODE_GO_API_KEY": "k",
    }
    problems = preflight.check(env, offline=True)
    assert any(
        p.check == "SWARM_PLANNER_FALLBACK_MODEL" and "paid fallback" in p.detail
        for p in problems
    )


def test_preflight_flags_a_fallback_for_the_wrong_provider_key():
    from swarm import preflight

    env = {
        "SWARM_PLANNER_MODEL": "opencode-go/glm-5.3-flash",
        "SWARM_CODER_MODEL": "opencode-go/glm-5.3-flash",
        "SWARM_REVIEWER_MODEL": "opencode-go/qwen3.8-flash",
        "SWARM_SENIOR_MODEL": "opencode-go/deepseek-v4-pro",
        "SWARM_PLANNER_FALLBACK_MODEL": "openrouter/nvidia/x:free",
        "SWARM_ALLOW_PAID": "1",
        "OPENCODE_GO_API_KEY": "k",
        "OPENROUTER_API_KEY": "",
    }
    problems = preflight.check(env, offline=True)
    assert any(
        p.check == "SWARM_PLANNER_FALLBACK_MODEL" and "OpenRouter" in p.detail
        for p in problems
    )
