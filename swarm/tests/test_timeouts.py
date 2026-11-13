"""Timeout economics tests (022 T3): fix calls get their own budget."""

from __future__ import annotations

from pathlib import Path

from swarm import llms
from swarm.events import llm_failure_type


def test_fix_timeout_default_and_override(monkeypatch):
    monkeypatch.delenv("SWARM_LLM_FIX_TIMEOUT_SECONDS", raising=False)
    assert llms._fix_timeout() == 180
    monkeypatch.setenv("SWARM_LLM_FIX_TIMEOUT_SECONDS", "240")
    assert llms._fix_timeout() == 240
    monkeypatch.setenv("SWARM_LLM_FIX_TIMEOUT_SECONDS", "nonsense")
    assert llms._fix_timeout() == 180


def test_a_fix_call_gets_the_long_timeout_and_chat_does_not(monkeypatch):
    monkeypatch.setenv("SWARM_CODER_MODEL", "openrouter/nvidia/nemotron-3.5-super-vl:free")
    monkeypatch.setenv("SWARM_LLM_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("SWARM_LLM_FIX_TIMEOUT_SECONDS", "180")
    assert llms.coder_llm().timeout == 90
    assert llms.coder_llm(fix=True).timeout == 180
    assert llms.senior_llm().timeout == 180


def test_a_timed_out_llm_call_is_its_own_event():
    assert llm_failure_type("Request timed out after 90s") == "llm_timeout"
    assert llm_failure_type("Timeout while reading response") == "llm_timeout"
    assert llm_failure_type("429 rate limit") == "llm_failed"


def test_retries_are_recorded_in_run_json():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "if attempt > 1:" in source
    assert "self.state.retries += 1" in source
    assert '"retries": self.state.retries' in source
