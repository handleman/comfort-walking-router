"""LLM factory (009 AC-1/AC-2, 012 T13). Every model id comes from env.

Routing by prefix: ollama/* → local Ollama, zen/* → OpenCode Zen gateway,
else OpenRouter. Paid models hard-blocked unless SWARM_ALLOW_PAID=1 AND
explicit allow_paid=True passed.

Fallbacks are opt-in at runtime: `activate_fallbacks()` switches subsequent
factory calls to `SWARM_<ROLE>_FALLBACK_MODEL` (or a local/cheap default), which
is how a quota/rate-limit hit survives without ending the pilot.
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

DEFAULT_OLLAMA = "http://localhost:11434"
DEFAULT_ZEN = "https://opencode.ai/zen/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_VERDICT_FALLBACK = "openrouter/nvidia/nemotron-3.5-super-vl:free"

_fallback_active = False

# First model whose paid-guard passes wins. Env `SWARM_<ROLE>_FALLBACK_MODEL`
# is prepended; the rest are safe defaults.
FALLBACK_CHAINS: dict[str, tuple[str, ...]] = {
    "SWARM_PLANNER_MODEL": ("ollama/qwen3.5:9b",),
    "SWARM_CODER_MODEL": ("ollama/qwen3.5:9b",),
    "SWARM_REVIEWER_MODEL": ("ollama/qwen3.5:9b",),
    # Zen's free tier is client-only, so the cloud fallback is cheap paid Zen;
    # without SWARM_ALLOW_PAID it falls through to local Qwen.
    "SWARM_SENIOR_MODEL": ("zen/glm-5.3-flash", "ollama/qwen3.5:9b"),
}


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


def activate_fallbacks() -> None:
    """Switch factory output to fallback models (called after a quota/429)."""
    global _fallback_active
    _fallback_active = True


def reset_fallbacks() -> None:
    global _fallback_active
    _fallback_active = False


def fallbacks_active() -> bool:
    return _fallback_active


def fallback_model(env_var: str, *, allow_paid: bool) -> str:
    """First usable fallback for a role; '' when none passes the paid guard."""
    name = env_var.removesuffix("_MODEL") + "_FALLBACK_MODEL"
    chain = tuple(x for x in (os.getenv(name, "").strip(),) if x) + FALLBACK_CHAINS.get(env_var, ())
    for model in chain:
        try:
            _guard(model, allow_paid=allow_paid)
        except PermissionError:
            continue
        return model
    return ""


def _build(model: str, *, temperature: float, allow_paid: bool) -> LLM:
    _guard(model, allow_paid=allow_paid)
    if model.startswith("ollama/"):
        return LLM(
            model=model,
            api_base=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA),
            temperature=temperature,
            # Qwen thinking blocks break tool-call parsing ("None or empty").
            # think:false must travel via LiteLLM: CrewAI's native
            # openai_compatible route drops extra_body, so force is_litellm.
            is_litellm=True,
            extra_body={"think": False},
        )
    if model.startswith("zen/"):
        return LLM(
            model=model.removeprefix("zen/"),
            custom_openai=True,  # gateway mode: keeps custom base_url
            base_url=os.getenv("SWARM_ZEN_BASE_URL", DEFAULT_ZEN),
            api_key=os.environ.get("OPENCODE_API_KEY", ""),
            temperature=temperature,
            timeout=120,
            max_retries=5,
        )
    return LLM(
        model=model,
        base_url=OPENROUTER_BASE,
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        temperature=temperature,
        timeout=120,
        max_retries=5,
    )


def _for_role(env_var: str, *, temperature: float, allow_paid: bool) -> LLM:
    model = _model(env_var)
    if _fallback_active:
        model = fallback_model(env_var, allow_paid=allow_paid) or model
    return _build(model, temperature=temperature, allow_paid=allow_paid)


def coder_llm() -> LLM:
    return _for_role("SWARM_CODER_MODEL", temperature=0, allow_paid=True)


def planner_llm(*, allow_paid: bool = False) -> LLM:
    return _for_role("SWARM_PLANNER_MODEL", temperature=0.2, allow_paid=allow_paid)


def reviewer_llm(*, allow_paid: bool = False) -> LLM:
    return _for_role("SWARM_REVIEWER_MODEL", temperature=0, allow_paid=allow_paid)


def senior_llm(*, allow_paid: bool = False) -> LLM:
    """Escalation brain: strong free-tier model (OpenRouter :free, tool-capable)."""
    return _for_role("SWARM_SENIOR_MODEL", temperature=0, allow_paid=allow_paid)


def zen_fallback_llm() -> LLM:
    """Explicit Zen gateway client (paid cheap model; needs SWARM_ALLOW_PAID=1)."""
    return _build(_model("SWARM_ZEN_FALLBACK_MODEL"), temperature=0, allow_paid=True)


def verdict_fallback_llm() -> LLM:
    """Free cloud model used only when the local QA model returns no verdict."""
    model = os.getenv("SWARM_VERDICT_FALLBACK_MODEL", DEFAULT_VERDICT_FALLBACK).strip()
    return _build(model, temperature=0, allow_paid=False)
