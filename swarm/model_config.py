"""047: one source of truth for model routing, the free predicate, and the roles.

Before this module the same knowledge lived in three places — `llms.provider_of`
and `preflight.provider` (routing), `usage.is_free`, `llms._guard` and
`preflight.is_free_model` (the free predicate), and the role list in
`llms.ROLE_MODEL_VARS` / `preflight.ROLE_VARS` / `flow._fallback_key`. The copies
drifted: a role could be known to one consumer and not another.

The operator-facing surface is unchanged: the same `SWARM_*_MODEL` env vars, the
same `.env`. Only the authority moved here. `resolve_models` returns a typed
`Profile` so the dashboard, preflight and the flow can read one object.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

# Prefix → provider. Anything else routes to OpenRouter.
PROVIDER_PREFIXES: tuple[tuple[str, str], ...] = (
    ("ollama/", "ollama"),
    ("zen/", "zen"),
    ("opencode-go/", "opencode-go"),
    ("openrouter/", "openrouter"),
)


def provider(model: str) -> str:
    """Provider a model id routes to (''/'?' → unknown)."""
    if not model or model == "?":
        return "unknown"
    for prefix, name in PROVIDER_PREFIXES:
        if model.startswith(prefix):
            return name
    return "openrouter"


def is_free(model: str) -> bool:
    """Local, `:free`, and `-free` ids never cost money."""
    return (
        model.startswith("ollama/")
        or ":free" in model
        or model.endswith("-free")
        or "contributor-free" in model
    )


@dataclass(frozen=True)
class Role:
    name: str
    model_var: str
    fallback_var: str
    optional: bool = False


# The single role table. `optional` means "documented default when unset" (the
# verifier inherits the senior model).
ROLES: tuple[Role, ...] = (
    Role("planner", "SWARM_PLANNER_MODEL", "SWARM_PLANNER_FALLBACK_MODEL"),
    Role("coder", "SWARM_CODER_MODEL", "SWARM_CODER_FALLBACK_MODEL"),
    Role("reviewer", "SWARM_REVIEWER_MODEL", "SWARM_REVIEWER_FALLBACK_MODEL"),
    Role("senior", "SWARM_SENIOR_MODEL", "SWARM_SENIOR_FALLBACK_MODEL"),
    Role("verifier", "SWARM_VERIFIER_MODEL", "SWARM_VERIFIER_FALLBACK_MODEL", optional=True),
)

# The two shapes consumers already imported (display order preserved).
ROLE_MODEL_VARS: tuple[tuple[str, str], ...] = tuple((r.name, r.model_var) for r in ROLES)
ROLE_VARS: tuple[str, ...] = tuple(r.model_var for r in ROLES if not r.optional)
OPTIONAL_ROLE_VARS: tuple[str, ...] = tuple(r.model_var for r in ROLES if r.optional)
FALLBACK_VARS: tuple[str, ...] = tuple(r.fallback_var for r in ROLES)

# 046 AC-3 / 047 AC-4: one knob per profile. A cloud-sized cap must never
# truncate an on-device step, and a local cap must never let a hung cloud call
# eat the task.
CREW_TIMEOUT_ENV = "SWARM_CREW_TIMEOUT_SECONDS"
LOCAL_CREW_TIMEOUT_ENV = "SWARM_LOCAL_CREW_TIMEOUT_SECONDS"
CLOUD_CREW_TIMEOUT = 300.0
LOCAL_CREW_TIMEOUT = 900.0


@dataclass(frozen=True)
class Model:
    role: str
    model: str
    fallback: str = ""
    provider: str = ""
    free: bool = False


@dataclass(frozen=True)
class Profile:
    models: dict[str, Model] = field(default_factory=dict)
    paid_allowed: bool = False
    # Resolved once from the same env snapshot as the models (047 AC-4).
    local: bool = False
    crew_timeout_seconds: float = CLOUD_CREW_TIMEOUT

    def crew_timeout(self) -> float:
        """Hard cap for one crew call, by profile (046 AC-3)."""
        return self.crew_timeout_seconds

    def role(self, name: str) -> Model:
        return self.models.get(name, Model(role=name, model=""))

    def primary(self, name: str) -> str:
        return self.role(name).model

    def fallback(self, name: str) -> str:
        return self.role(name).fallback


def _positive_seconds(raw: object) -> float:
    try:
        value = float(str(raw or "").strip())
    except (TypeError, ValueError):
        return 0.0
    return value if value > 0 else 0.0


def resolve_models(env: Mapping[str, str] | None = None) -> Profile:
    """Resolve every role from the environment (the same `.env` as today)."""
    source: Mapping[str, str] = os.environ if env is None else env
    out: dict[str, Model] = {}
    for role in ROLES:
        model = str(source.get(role.model_var, "")).strip()
        if not model and role.name == "verifier":
            model = str(source.get("SWARM_SENIOR_MODEL", "")).strip()
        fallback = str(source.get(role.fallback_var, "")).strip()
        if not fallback:
            fallback = str(source.get("SWARM_LOCAL_FALLBACK_MODEL", "")).strip()
        out[role.name] = Model(
            role=role.name,
            model=model,
            fallback=fallback,
            provider=provider(model),
            free=is_free(model),
        )
    local = any(
        str(m.model or "").startswith("ollama/")
        or str(m.fallback or "").startswith("ollama/")
        for m in out.values()
    )
    if local:
        timeout = _positive_seconds(source.get(LOCAL_CREW_TIMEOUT_ENV)) or LOCAL_CREW_TIMEOUT
    else:
        timeout = _positive_seconds(source.get(CREW_TIMEOUT_ENV)) or CLOUD_CREW_TIMEOUT
    return Profile(
        models=out,
        paid_allowed=str(source.get("SWARM_ALLOW_PAID", "0")).strip() == "1",
        local=local,
        crew_timeout_seconds=timeout,
    )


def main() -> int:
    """`python -m swarm.model_config` — the resolved profile the run uses (AC-5)."""
    from pathlib import Path

    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass
    profile = resolve_models()
    print(f"{'role':9} {'model':46} {'provider':12} {'cost':5} fallback")
    for role in ROLES:
        m = profile.role(role.name)
        print(
            f"{role.name:9} {m.model or '<unset>':46} {m.provider or '-':12} "
            f"{'free' if m.free else 'paid':5} {m.fallback or '-'}"
        )
    print(
        f"profile={'local' if profile.local else 'cloud'} "
        f"crew_timeout={profile.crew_timeout():.0f}s paid_allowed={profile.paid_allowed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
