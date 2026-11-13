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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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

# Roles (identified by their `*_MODEL` env var) that have fallen back. A
# transport blip in one role must not degrade the others: 007-T4 lost a run
# because a coder timeout switched QA to a 9B general model that could not
# review, so it never declared a verdict (needs_human, 30 minutes).
_fallback_roles: set[str] = set()

# One local model every role falls back to when its cloud provider is not
# reachable. Configurable like the role models: `SWARM_LOCAL_FALLBACK_MODEL`.
DEFAULT_LOCAL_FALLBACK = "ollama/swarm-coder:latest"


def local_fallback_model() -> str:
    """The shared local fallback; empty env falls back to the default."""
    return (
        os.getenv("SWARM_LOCAL_FALLBACK_MODEL", DEFAULT_LOCAL_FALLBACK).strip()
        or DEFAULT_LOCAL_FALLBACK
    )


def default_fallback_chain(env_var: str) -> tuple[str, ...]:
    """Default chain per role; a cloud outage lands on the configured local model.

    Senior keeps cheap paid Zen first (it is the escalation brain, and Zen's free
    tier is client-only). Every other role goes straight to the local fallback.
    """
    local = local_fallback_model()
    if env_var == "SWARM_SENIOR_MODEL":
        return ("zen/glm-5.3-flash", local)
    return (local,)


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


# Roles shown by the dashboard, in display order.
ROLE_MODEL_VARS: tuple[tuple[str, str], ...] = (
    ("planner", "SWARM_PLANNER_MODEL"),
    ("coder", "SWARM_CODER_MODEL"),
    ("reviewer", "SWARM_REVIEWER_MODEL"),
    ("senior", "SWARM_SENIOR_MODEL"),
    ("verifier", "SWARM_VERIFIER_MODEL"),
)


def verifier_model(env: Mapping[str, str] | None = None) -> str:
    """The verifier's model id: its own role, else the senior/free brain (019).

    The verifier has to reason, not count, so it defaults to the strongest free
    model the harness already configures. Without `SWARM_VERIFIER_MODEL` there is
    no second id to keep working.
    """
    source = os.environ if env is None else env
    return (
        source.get("SWARM_VERIFIER_MODEL", "").strip()
        or source.get("SWARM_SENIOR_MODEL", "").strip()
    )


def _primary_model(role: str, env_var: str) -> str:
    primary = os.getenv(env_var, "").strip()
    if not primary and role == "verifier":
        primary = os.getenv("SWARM_SENIOR_MODEL", "").strip()
    return primary


def role_models() -> list[dict[str, Any]]:
    """Effective model per role, so the dashboard stops showing a static list.

    A paid role that fell back to local Ollama must *look* local: same source of
    truth as `_for_role`, so the display cannot drift from what is actually called.
    """
    out: list[dict[str, Any]] = []
    for role, var in ROLE_MODEL_VARS:
        primary = _primary_model(role, var)
        fallback = ""
        if fallbacks_active(var):
            fallback = fallback_model(var, allow_paid=_allow_paid())
        model = fallback or primary or "?"
        out.append(
            {
                "role": role,
                "primary": primary,
                "model": model,
                "fallback": bool(fallback and fallback != primary),
            }
        )
    return out


def fallback_roles() -> list[str]:
    """Role env vars currently running a fallback model ("*" means all of them)."""
    if "*" in _fallback_roles:
        return [var for _, var in ROLE_MODEL_VARS]
    return sorted(r for r in _fallback_roles if r != "*")


def fallback_model(env_var: str, *, allow_paid: bool) -> str:
    """First usable fallback for a role; '' when none passes the paid guard."""
    name = env_var.removesuffix("_MODEL") + "_FALLBACK_MODEL"
    chain = tuple(x for x in (os.getenv(name, "").strip(),) if x) + default_fallback_chain(env_var)
    for model in chain:
        try:
            _guard(model, allow_paid=allow_paid)
        except PermissionError:
            continue
        return model
    return ""


# ---------------------------------------------------------------------------
# Prompt-cache capability (020 T3)
# ---------------------------------------------------------------------------
# Prefix caching is a provider feature, and how it is enabled differs:
#   ollama/*      — automatic KV reuse for an identical prefix; nothing to send.
#   openrouter/*  — automatic for supporting models (usage reports
#                   `prompt_tokens_details.cached_tokens`); nothing to send.
#   zen/*         — the gateway does not cache; no hint exists.
#   anthropic/*   — a direct Anthropic call accepts an ephemeral `cache_control`
#                   hint; it is attached when the call succeeds, and a provider
#                   that rejects the field falls back to the plain LLM.
# The real enabler is the byte-stable prefix from 020 T2: a prompt that
# reassembles its own head cannot be cached whatever we send.

_cache_modes: dict[str, str] = {}


def prompt_cache_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get("SWARM_PROMPT_CACHE", "1")).strip().lower() not in {"0", "false", "no"}


def cache_support(model: str) -> str:
    """`auto` (provider caches an identical prefix), `hint` (we can ask),
    `none` (no cache) or `off` (SWARM_PROMPT_CACHE=0)."""
    if not prompt_cache_enabled():
        return "off"
    if model.startswith("zen/"):
        return "none"
    if model.startswith(("openrouter/", "ollama/")):
        return "auto"
    if model.startswith("anthropic/") or "claude" in model:
        return "hint"
    return "auto"


def _record_cache_mode(model: str, mode: str) -> None:
    _cache_modes[model] = mode


def cache_modes() -> dict[str, str]:
    """What was decided per model this process; recorded in `run.json.cache`."""
    return dict(_cache_modes)


def _timeout_seconds() -> int:
    """Per-request HTTP timeout. Lower it when the network is flaky; raise for slow local models."""
    try:
        return max(15, int(os.getenv("SWARM_LLM_TIMEOUT_SECONDS", "180") or 180))
    except ValueError:
        return 180


def _fix_timeout() -> int:
    """Timeout for fix/senior/verifier calls (022 AC-5).

    A fix generation is not a 1–7 s chat call: 90 s cut real fixes off (the
    007-T5 lesson), and the bake-off showed a 90 s Zen timeout causing a retry
    that doubled the task. Chat-like calls keep the shorter default.
    """
    try:
        return max(30, int(os.getenv("SWARM_LLM_FIX_TIMEOUT_SECONDS", "180") or 180))
    except ValueError:
        return 180


def _build(
    model: str, *, temperature: float, allow_paid: bool, timeout: int | None = None
) -> LLM:
    _guard(model, allow_paid=allow_paid)
    support = cache_support(model)
    # The harness owns retries (backoff + fallback models); SDK-level retries of a
    # dead endpoint just multiply the wait (5 × timeout before the flow sees it).
    sdk_retries = int(os.getenv("SWARM_LLM_MAX_RETRIES", "0") or 0)
    if model.startswith("ollama/"):
        try:
            ollama_timeout = max(30, int(os.getenv("SWARM_OLLAMA_TIMEOUT_SECONDS", "1800") or 1800))
        except ValueError:
            ollama_timeout = 1800
        _record_cache_mode(model, support)
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
        _record_cache_mode(model, support)
        return LLM(
            model=model.removeprefix("zen/"),
            custom_openai=True,  # gateway mode: keeps custom base_url
            base_url=os.getenv("SWARM_ZEN_BASE_URL", DEFAULT_ZEN),
            api_key=os.environ.get("OPENCODE_API_KEY", ""),
            temperature=temperature,
            timeout=timeout or _timeout_seconds(),
            max_retries=sdk_retries,
        )
    if support == "hint":
        try:
            llm = LLM(
                model=model,
                base_url=OPENROUTER_BASE,
                api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                temperature=temperature,
                timeout=timeout or _timeout_seconds(),
                max_retries=sdk_retries,
                extra_body={"cache_control": {"type": "ephemeral"}},
            )
            _record_cache_mode(model, "hint")
            return llm
        except Exception:
            # A provider that rejects the field must not break the run: the
            # plain call still works, it just does not get the discount.
            _record_cache_mode(model, "plain")
    else:
        _record_cache_mode(model, support)
    return LLM(
        model=model,
        base_url=OPENROUTER_BASE,
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        temperature=temperature,
        timeout=timeout or _timeout_seconds(),
        max_retries=sdk_retries,
    )


def _for_role(
    env_var: str, *, temperature: float, allow_paid: bool, timeout: int | None = None
) -> LLM:
    model = _model(env_var)
    if fallbacks_active(env_var):
        model = fallback_model(env_var, allow_paid=allow_paid) or model
    return _build(model, temperature=temperature, allow_paid=allow_paid, timeout=timeout)


def coder_llm(*, fix: bool = False) -> LLM:
    return _for_role(
        "SWARM_CODER_MODEL",
        temperature=0,
        allow_paid=True,
        timeout=_fix_timeout() if fix else None,
    )


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
    return _for_role(
        "SWARM_SENIOR_MODEL", temperature=0, allow_paid=allow_paid, timeout=_fix_timeout()
    )


def verifier_llm(*, allow_paid: bool = False) -> LLM:
    """Scenario verifier (019): read the whole scenario and judge, not count.

    `SWARM_VERIFIER_MODEL` wins; without it the senior/free brain is used, so
    enabling the phase adds no second model id to keep working. Free only by
    default: a paid model must not become the verifier of record.
    """
    model = verifier_model()
    if not model:
        raise RuntimeError(
            "SWARM_VERIFIER_MODEL (or SWARM_SENIOR_MODEL) is not set; set one "
            "to enable the scenario verifier."
        )
    if fallbacks_active("SWARM_VERIFIER_MODEL"):
        model = fallback_model("SWARM_VERIFIER_MODEL", allow_paid=allow_paid) or model
    return _build(model, temperature=0, allow_paid=allow_paid, timeout=_fix_timeout())


def conflict_llm(*, allow_paid: bool = True) -> LLM:
    """Merge-conflict resolver (016): the coder brain unless overridden.

    `SWARM_CONFLICT_MODEL` is optional; without it the coder model is reused, so
    there is no second model to keep working. Per-role fallbacks apply.
    """
    configured = os.getenv("SWARM_CONFLICT_MODEL", "").strip()
    model = configured or os.getenv("SWARM_CODER_MODEL", "").strip()
    if fallbacks_active("SWARM_CONFLICT_MODEL"):
        model = fallback_model("SWARM_CONFLICT_MODEL", allow_paid=allow_paid) or model
    return _build(model, temperature=0, allow_paid=allow_paid, timeout=_fix_timeout())


def verdict_fallback_llm() -> LLM:
    """Verdict-only reviewer, used when the local QA model returns no verdict.

    It is the senior model: the strongest free tool-capable brain we already
    configure, so a missing verdict is decided by the same model that reasons
    about hard fixes instead of a second, separately-maintained id. Free only:
    a paid model must never become the reviewer of record.
    """
    return _for_role("SWARM_SENIOR_MODEL", temperature=0, allow_paid=False)
