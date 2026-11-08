from swarm.usage import (
    budget_note,
    env_float,
    env_int,
    estimate_cost,
    estimate_run_cost,
    is_free,
)


def test_free_models_cost_zero():
    assert is_free("ollama/swarm-coder:latest")
    assert is_free("openrouter/nvidia/x:free")
    assert is_free("zen/some-free")
    assert estimate_cost({"ollama/swarm-coder:latest": (1000, 500)}) == 0.0
    assert estimate_cost({"openrouter/nvidia/x:free": (10**6, 10**6)}) == 0.0


def test_known_paid_price_is_estimated():
    cost = estimate_cost({"zen/glm-5.3-flash": (1_000_000, 1_000_000)})
    assert cost == 0.4  # (0.10 + 0.30)


def test_price_lookup_survives_stripped_prefix():
    # CrewAI's LLM.model drops the `zen/` routing prefix.
    assert estimate_cost({"glm-5.3-flash": (1_000_000, 0)}) == 0.1


def test_unknown_paid_price_is_none_not_fake_zero():
    assert estimate_cost({"openrouter/vendor/mystery": (100, 100)}) is None


def test_run_cost_handles_mixed_models():
    assert estimate_run_cost([], 0, 0) == 0.0
    assert estimate_run_cost(["ollama/x", "openrouter/y:free"], 1000, 500) == 0.0
    only_paid = estimate_run_cost(["ollama/x", "zen/glm-5.3-flash"], 0, 0)
    assert only_paid == 0.0
    two_paid = estimate_run_cost(["zen/glm-5.3-flash", "zen/deepseek-v4.1-flash"], 1000, 5)
    assert two_paid is None


def test_budget_note_reports_each_limit():
    common = {
        "total_tokens": 100,
        "cost_usd": 0.0,
        "elapsed_seconds": 5,
        "max_tokens": 0,
        "max_cost_usd": 0,
        "max_seconds": 0,
    }
    assert budget_note(**common) == ""
    assert "token budget" in budget_note(**{**common, "max_tokens": 50})
    assert "cost budget" in budget_note(**{**common, "cost_usd": 0.2, "max_cost_usd": 0.1})
    assert "time budget" in budget_note(**{**common, "elapsed_seconds": 900, "max_seconds": 60})
    # Unknown cost can never trip the cost budget (no guessing).
    assert budget_note(**{**common, "cost_usd": None, "max_cost_usd": 0.01}) == ""


def test_env_parsing_is_forgiving(monkeypatch):
    monkeypatch.setenv("X_INT", "12.0")
    monkeypatch.setenv("X_FLOAT", "0.25")
    monkeypatch.setenv("X_BAD", "nope")
    assert env_int("X_INT", 1) == 12
    assert env_float("X_FLOAT", 1.0) == 0.25
    assert env_int("X_BAD", 3) == 3
    assert env_float("X_MISSING", 1.5) == 1.5
