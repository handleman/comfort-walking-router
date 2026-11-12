"""Prompt-cache capability tests (020 T3): hint where supported, never break a run."""

from __future__ import annotations

from swarm import llms


def test_capability_table_matches_the_providers_we_route(monkeypatch):
    monkeypatch.delenv("SWARM_PROMPT_CACHE", raising=False)
    assert llms.cache_support("ollama/qwen3.5:9b") == "auto"
    assert llms.cache_support("openrouter/nvidia/nemotron:free") == "auto"
    assert llms.cache_support("zen/glm-5.3-flash") == "none"
    assert llms.cache_support("anthropic/claude-opus-5") == "hint"


def test_off_switch_disables_every_hint(monkeypatch):
    monkeypatch.setenv("SWARM_PROMPT_CACHE", "0")
    assert llms.cache_support("ollama/qwen3.5:9b") == "off"
    assert llms.cache_support("anthropic/claude-opus-5") == "off"
    assert llms.prompt_cache_enabled() is False
    monkeypatch.setenv("SWARM_PROMPT_CACHE", "1")
    assert llms.prompt_cache_enabled() is True


def test_building_an_ollama_llm_records_auto(monkeypatch):
    monkeypatch.delenv("SWARM_PROMPT_CACHE", raising=False)
    llms._build("ollama/qwen3.5:9b", temperature=0, allow_paid=False)
    assert llms.cache_modes()["ollama/qwen3.5:9b"] == "auto"


def test_a_rejected_hint_falls_back_to_the_plain_llm(monkeypatch):
    monkeypatch.delenv("SWARM_PROMPT_CACHE", raising=False)
    calls: list[dict] = []
    real = llms.LLM

    def fake_llm(**kwargs):
        calls.append(kwargs)
        if "extra_body" in kwargs:
            raise ValueError("provider does not accept cache_control")
        return object()

    monkeypatch.setattr(llms, "LLM", fake_llm)
    try:
        llms._build("anthropic/claude-opus-5", temperature=0, allow_paid=True)
    finally:
        monkeypatch.setattr(llms, "LLM", real)
    assert len(calls) == 2
    assert "extra_body" in calls[0] and "extra_body" not in calls[1]
    assert llms.cache_modes()["anthropic/claude-opus-5"] == "plain"


def test_an_accepted_hint_is_recorded(monkeypatch):
    monkeypatch.delenv("SWARM_PROMPT_CACHE", raising=False)
    real = llms.LLM
    monkeypatch.setattr(llms, "LLM", lambda **kwargs: object())
    try:
        llms._build("anthropic/claude-opus-5", temperature=0, allow_paid=True)
    finally:
        monkeypatch.setattr(llms, "LLM", real)
    assert llms.cache_modes()["anthropic/claude-opus-5"] == "hint"


def test_run_json_records_the_cache_decision():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert '"cache": {' in source
    assert '"cached_prompt_tokens": self.state.cached_prompt_tokens' in source
