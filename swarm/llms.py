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

# Roles (identified by their `*_MODEL` env var) that have fallen back. A
# transport blip in one role must not degrade the others: 007-T4 lost a run
# because a coder timeout switched QA to a 9B general model that could not
# review, so it never declared a verdict (needs_human, 30 minutes).
_fallback_roles: set[str] = set()

# First model whose paid-guard passes wins. Env `SWARM_<ROLE>_FALLBACK_MODEL`
# is prepended; the rest are safe defaults.
FALLBACK_CHAINS: dict[str, tuple[str, ...]] = {
    "SWARM_PLANNER_MODEL": ("ollama/qwen3.5:9b",),
    # Purpose-built local coder first; the generic 9B model only as a last resort.
    "SWARM_CODER_MODEL": ("ollama/swarm-coder:latest", "ollama/qwen3.5:9b"),
    # The reviewer is *already* local; a weaker general model cannot run gates or
    # emit a verdict. No chain: a missing verdict is handled by
    # `verdict_fallback_llm`, never by silently downgrading QA.
    "SWARM_REVIEWER_MODEL": (),
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


def activate_fallbacks(role: str | None = None) -> None:
    """Switch one role to its fallback chain; no argument switches every role.

    A provider-wide quota wall justifies activating all roles; a single
    role's transport failure must only move that role.
    """
    if role is None:
        _fallback_roles.add("*")
    else:
        _fallback_roles.add(role)


def reset_fallbacks() -> None:
    _fallback_roles.clear()


def fallbacks_active(role: str | None = None) -> bool:
    if role is None:
        return bool(_fallback_roles)
    return "*" in _fallback_roles or role in _fallback_roles


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


def _timeout_seconds() -> int:
    """Per-request HTTP timeout. Lower it when the network is flaky; raise for slow local models."""
    try:
        return max(15, int(os.getenv("SWARM_LLM_TIMEOUT_SECONDS", "180") or 180))
    except ValueError:
        return 180


def _build(model: str, *, temperature: float, allow_paid: bool) -> LLM:
    _guard(model, allow_paid=allow_paid)
    # The harness owns retries (backoff + fallback models); SDK-level retries of a
    # dead endpoint just multiply the wait (5 × timeout before the flow sees it).
    sdk_retries = int(os.getenv("SWARM_LLM_MAX_RETRIES", "0") or 0)
    if model.startswith("ollama/"):
        try:
            ollama_timeout = max(30, int(os.getenv("SWARM_OLLAMA_TIMEOUT_SECONDS", "300") or 300))
        except ValueError:
            ollama_timeout = 300
        return LLM(
            model=model,
            api_base=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA),
            temperature=temperature,
            timeout=ollama_timeout,
            max_retries=1,
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
            timeout=_timeout_seconds(),
            max_retries=sdk_retries,
        )
    return LLM(
        model=model,
        base_url=OPENROUTER_BASE,
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        temperature=temperature,
        timeout=_timeout_seconds(),
        max_retries=sdk_retries,
    )


def _for_role(env_var: str, *, temperature: float, allow_paid: bool) -> LLM:
    model = _model(env_var)
    if fallbacks_active(env_var):
        model = fallback_model(env_var, allow_paid=allow_paid) or model
    return _build(model, temperature=temperature, allow_paid=allow_paid)


def coder_llm() -> LLM:
    return _for_role("SWARM_CODER_MODEL", temperature=0, allow_paid=True)


def local_coder_llm() -> LLM:
    """Free local coder for trivial micro-steps (015 D2)."""
    model = os.getenv("SWARM_LOCAL_CODER_MODEL", "ollama/swarm-coder:latest").strip()
    return _build(model, temperature=0, allow_paid=False)


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
