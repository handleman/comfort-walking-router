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
