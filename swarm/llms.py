"""LLM factory (009 AC-1/AC-2). No hardcoded models: every model id comes from env.

Routing by prefix: ollama/* → local Ollama, zen/* → OpenCode Zen gateway,
else OpenRouter. Paid models hard-blocked unless SWARM_ALLOW_PAID=1 AND
explicit allow_paid=True passed.
"""

from __future__ import annotations

import os

from pathlib import Path

from crewai import LLM

try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass


def _allow_paid() -> bool:
    return os.getenv("SWARM_ALLOW_PAID", "0") == "1"


def _model(env_var: str) -> str:
    """Required model id from env — no hardcoded fallbacks."""
    model = os.getenv(env_var, "")
    if not model:
        raise RuntimeError(
            f"{env_var} is not set. Copy .env.example to .env and set every SWARM_*_MODEL."
        )
    return model


def _guard(model: str, *, allow_paid: bool) -> None:
    if ":free" in model or model.startswith("ollama/") or "contributor-free" in model or model.endswith("-free"):
        return
    if _allow_paid() and allow_paid:
        return
    raise PermissionError(
        f"Paid model blocked: {model}. Set SWARM_ALLOW_PAID=1 and pass allow_paid=True to opt in."
    )


def coder_llm() -> LLM:
    model = _model("SWARM_CODER_MODEL")
    _guard(model, allow_paid=True)
    return LLM(
        model=model,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
        # Qwen thinking blocks break LiteLLM tool-call parsing ("None or empty");
        # think:false restores native tool_calls (verified 2026-10-10).
        extra_body={"think": False},
    )


def _openrouter_llm(env_var: str, *, temperature: float, allow_paid: bool = False) -> LLM:
    model = _model(env_var)
    _guard(model, allow_paid=allow_paid)
    if model.startswith("ollama/"):  # local override: same factory, no cloud calls
        return LLM(
            model=model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
            extra_body={"think": False},  # see coder_llm note: thinking breaks tool_calls
        )
    if model.startswith("zen/"):  # OpenCode Zen free tier, e.g. zen/<free-chat-model>
        return LLM(
            model=model.removeprefix("zen/"),
            custom_openai=True,  # gateway mode: keeps custom base_url (verified 2026-10-10)
            base_url=os.getenv("SWARM_ZEN_BASE_URL", "https://opencode.ai/zen/v1"),
            api_key=os.environ.get("OPENCODE_API_KEY", ""),
            temperature=temperature,
            timeout=120,
            max_retries=5,
        )
    return LLM(
        model=model,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        temperature=temperature,
        timeout=120,
        max_retries=5,
    )


def planner_llm(*, allow_paid: bool = False) -> LLM:
    return _openrouter_llm(
        "SWARM_PLANNER_MODEL",
        temperature=0.2,
        allow_paid=allow_paid,
    )


def reviewer_llm(*, allow_paid: bool = False) -> LLM:
    return _openrouter_llm(
        "SWARM_REVIEWER_MODEL",
        temperature=0,
        allow_paid=allow_paid,
    )


def zen_fallback_llm() -> LLM:
    model = _model("SWARM_ZEN_FALLBACK_MODEL")
    _guard(model, allow_paid=True)  # free-tier id passes guard
    return LLM(
        model=model,
        base_url=os.getenv("SWARM_ZEN_BASE_URL", "https://opencode.ai/zen/v1"),
        api_key=os.environ.get("OPENCODE_API_KEY", ""),
        temperature=0,
        timeout=120,
        max_retries=5,
    )
