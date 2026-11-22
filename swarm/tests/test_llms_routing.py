"""Local-Ollama LLMs must route via LiteLLM, not CrewAI's native client.

CrewAI's native openai_compatible route drops `extra_body`, so `think:false`
never reached Ollama: Qwen thought mid-tool-call and every native response
came back empty ("Invalid response from LLM call - None or empty",
2026-10-10, pilot 001-T1 step 5). `is_litellm=True` keeps the mitigation live.
"""

from swarm.llms import coder_llm, planner_llm


def test_coder_uses_litellm_transport(monkeypatch):
    monkeypatch.setenv("SWARM_CODER_MODEL", "ollama/swarm-coder:latest")
    llm = coder_llm()
    assert llm.is_litellm is True
    assert llm.additional_params.get("extra_body") == {"think": False}


def test_local_override_uses_litellm_transport(monkeypatch):
    monkeypatch.setenv("SWARM_PLANNER_MODEL", "ollama/qwen3.5:9b")
    llm = planner_llm()
    assert llm.is_litellm is True
    assert llm.additional_params.get("extra_body") == {"think": False}


def test_a_paid_planner_needs_the_global_opt_in(monkeypatch):
    """014-T6: a paid planner id must be blocked unless the operator opted in.

    One switch (2026-11-22): `SWARM_ALLOW_PAID=1` decides. The per-call
    `allow_paid=` flag is accepted for compatibility but no longer gates, so the
    same call cannot fail at run time because a builder passed the wrong flag.
    """
    import pytest

    monkeypatch.setenv("SWARM_PLANNER_MODEL", "openrouter/deepseek/deepseek-v4.1-flash-1017")
    monkeypatch.setenv("SWARM_ALLOW_PAID", "0")
    with pytest.raises(PermissionError):
        planner_llm(allow_paid=True)

    monkeypatch.setenv("SWARM_ALLOW_PAID", "1")
    assert planner_llm(allow_paid=True).model == "deepseek/deepseek-v4.1-flash-1017"


def test_the_plan_crew_passes_the_paid_opt_in():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "crew.py").read_text()
    assert "llm=planner_llm(allow_paid=True)" in source
