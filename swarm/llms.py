"""Free-first LLM factory (009 AC-1/AC-2). Single place auditing model routing.

Tiers: Coder=local Ollama Qwen (always free/local), Planner/Reviewer=OpenRouter
:free ordered fallback, Zen free as fallback. Paid models hard-blocked unless
SWARM_ALLOW_PAID=1 AND explicit allow_paid=True passed.
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


def _guard(model: str, *, allow_paid: bool) -> None:
    if ":free" in model or model.startswith("ollama/") or "contributor-free" in model or model.endswith("-free"):
        return
    if _allow_paid() and allow_paid:
        return
    raise PermissionError(
        f"Paid model blocked: {model}. Set SWARM_ALLOW_PAID=1 and pass allow_paid=True to opt in."
    )


def coder_llm() -> LLM:
    model = os.getenv("SWARM_CODER_MODEL", "ollama/qwen3.5:9b")
    _guard(model, allow_paid=True)  # ollama passes guard; explicit anyway
    return LLM(
        model=model,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
        # Qwen thinking blocks break LiteLLM tool-call parsing ("None or empty");
        # think:false restores native tool_calls (verified 2026-10-10).
        extra_body={"think": False},
    )


def _openrouter_llm(env_var: str, default: str, *, temperature: float, allow_paid: bool = False) -> LLM:
    model = os.getenv(env_var, default)
    _guard(model, allow_paid=allow_paid)
    if model.startswith("ollama/"):  # local override: same factory, no cloud calls
        return LLM(
            model=model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
            extra_body={"think": False},  # see coder_llm note: thinking breaks tool_calls
        )
    if model.startswith("zen/"):  # OpenCode Zen free tier, e.g. zen/space-bunny-free
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
        "ollama/qwen3.5:9b",
        temperature=0.2,
        allow_paid=allow_paid,
    )


def reviewer_llm(*, allow_paid: bool = False) -> LLM:
    return _openrouter_llm(
        "SWARM_REVIEWER_MODEL",
        "ollama/qwen3.5:9b",
        temperature=0,
        allow_paid=allow_paid,
    )


def zen_fallback_llm() -> LLM:
    model = os.getenv("SWARM_ZEN_FALLBACK_MODEL", "openai/muse-spark-1.3-contributor-free")
    _guard(model, allow_paid=True)  # free-tier id passes guard
    return LLM(
        model=model,
        base_url=os.getenv("SWARM_ZEN_BASE_URL", "https://opencode.ai/zen/v1/chat/completions"),
        api_key=os.environ.get("OPENCODE_API_KEY", ""),
        temperature=0,
        timeout=120,
        max_retries=5,
    )
