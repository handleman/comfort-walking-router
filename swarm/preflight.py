"""Preflight before the first LLM call (012 T12).

Checks that the configured roles can actually run: env model ids, provider
keys, Ollama reachability + pulled image, cloud model availability, the two
venvs, and the gate binaries. Never prints secret values.

Run standalone: `make swarm-preflight` (or `python -m swarm.preflight`).
Set `SWARM_SKIP_PREFLIGHT=1` to bypass inside a pilot.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# Roles that the crew actually instantiates (zen fallback is Phase 1 / T13).
ROLE_VARS = (
    "SWARM_PLANNER_MODEL",
    "SWARM_CODER_MODEL",
    "SWARM_REVIEWER_MODEL",
    "SWARM_SENIOR_MODEL",
)
GATE_BINARIES = ("pytest", "ruff", "mypy")


def _gate_binaries(env: dict[str, str]) -> tuple[str, ...]:
    """First executable of each `SWARM_GATE_COMMANDS` entry (or Python defaults)."""
    raw = env.get("SWARM_GATE_COMMANDS", "").strip()
    if not raw:
        return GATE_BINARIES
    binaries: list[str] = []
    for command in re.split(r"[;\n]", raw):
        try:
            argv = shlex.split(command)
        except ValueError:
            continue
        if argv:
            binaries.append(argv[0])
    return tuple(dict.fromkeys(binaries)) or GATE_BINARIES
OPTIONAL_BINARIES = ("npm",)  # frontend gate only when vitest is installed

DEFAULT_OLLAMA = "http://localhost:11434"
DEFAULT_ZEN = "https://opencode.ai/zen/v1"
USER_AGENT = "comfort-walking-router/0.1 (swarm-preflight)"
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"


@dataclass(frozen=True)
class Problem:
    check: str
    detail: str

    def __str__(self) -> str:
        return f"{self.check}: {self.detail}"


def provider(model: str) -> str:
    if model.startswith("ollama/"):
        return "ollama"
    if model.startswith("zen/"):
        return "zen"
    return "openrouter"


def model_id(model: str) -> str:
    for prefix in ("ollama/", "zen/", "openrouter/"):
        if model.startswith(prefix):
            return model.removeprefix(prefix)
    return model


def is_free_model(model: str) -> bool:
    """Mirror of `swarm.llms._guard` (free prefixes/policies)."""
    return (
        ":free" in model
        or model.startswith("ollama/")
        or "contributor-free" in model
        or model.endswith("-free")
    )


def _get_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 8.0) -> Any:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _ping_model_ids(env: dict[str, str], fetch: Callable[..., Any]) -> dict[str, set[str]]:
    """Available model ids per cloud provider (one request each)."""
    avail: dict[str, set[str]] = {}
    if any(provider(env.get(v, "")) == "openrouter" for v in ROLE_VARS):
        try:
            data = fetch(OPENROUTER_MODELS)
        except Exception as e:
            raise RuntimeError(f"openrouter model list: {e}") from e
        avail["openrouter"] = {m["id"] for m in data.get("data", [])}
    if any(provider(env.get(v, "")) == "zen" for v in ROLE_VARS):
        base = env.get("SWARM_ZEN_BASE_URL", DEFAULT_ZEN).rstrip("/")
        try:
            data = fetch(
                f"{base}/models",
                headers={"Authorization": f"Bearer {env.get('OPENCODE_API_KEY', '')}"},
            )
        except Exception as e:
            raise RuntimeError(f"zen model list: {e}") from e
        avail["zen"] = {m["id"] for m in data.get("data", [])}
    return avail


def _available_ollama(base: str, fetch: Callable[..., Any]) -> set[str]:
    data = fetch(f"{base.rstrip('/')}/api/tags")
    names: set[str] = set()
    for m in data.get("models", []):
        name = m.get("name") or m.get("model") or ""
        if name:
            names.add(name.removesuffix(":latest"))
    return names


def _run(cmd: list[str], timeout: int) -> bool:
    try:
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout, check=False
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def self_heal(
    env: dict[str, str] | None = None,
    *,
    log: Callable[[str], None] = print,
) -> list[str]:
    """Best-effort environment repair before checks (015 AC-10).

    Only missing local artefacts are rebuilt; auth/base-URL failures stay
    terminal because nothing local can fix them.
    """
    env = dict(os.environ if env is None else env)
    if env.get("SWARM_SELF_HEAL", "1") != "1":
        return []
    actions: list[str] = []
    root = REPO_ROOT
    needs_venv = not (root / ".venv" / "bin" / "python").exists()
    if needs_venv and _run(["make", "dev-setup-python"], timeout=900):
        actions.append("bootstrapped .venv")
    needs_frontend = (root / "frontend" / "package.json").is_file() and not (
        root / "frontend" / "node_modules"
    ).is_dir()
    if needs_frontend and _run(["npm", "--prefix", "frontend", "ci"], timeout=900):
        actions.append("installed frontend deps")
    else:
        # A task added a devDependency (e.g. vitest in 007-T1) but the coder cannot
        # run `npm install`; install it here so the gate sees the dependency.
        deps_missing = (root / "frontend" / "node_modules").is_dir() and not _run(
            ["npm", "--prefix", "frontend", "ls", "--depth=0"], timeout=120
        )
        if deps_missing and _run(["npm", "--prefix", "frontend", "install"], timeout=900):
            actions.append("installed newly added frontend deps")
    modelfiles = {
        "swarm-qa": root / "swarm" / "ollama" / "Modelfile.qa",
        "swarm-coder": root / "swarm" / "ollama" / "Modelfile",
    }
    for var in ROLE_VARS:
        model = env.get(var, "").strip()
        if provider(model) != "ollama":
            continue
        name = model_id(model).removesuffix(":latest")
        modelfile = modelfiles.get(name)
        if modelfile is None or not modelfile.is_file():
            continue
        if _run(["ollama", "show", name], timeout=30):
            continue
        if _run(["ollama", "create", name, "-f", str(modelfile)], timeout=600):
            actions.append(f"built ollama image {name}")
    for action in actions:
        log(f"self-heal: {action}")
    return actions


def unmerged_paths(repo_root: Path | None = None) -> list[str]:
    """Paths with unresolved index stages (mid-merge, rebase, or stash pop)."""
    try:
        p = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=repo_root or REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted({line.strip() for line in p.stdout.splitlines() if line.strip()})


def check(
    env: dict[str, str] | None = None,
    *,
    fetch: Callable[..., Any] = _get_json,
    which: Callable[[str], str | None] = shutil.which,
    offline: bool = False,
) -> list[Problem]:
    """Return every blocking problem; empty list means safe to start."""
    env = dict(os.environ if env is None else env)
    self_heal(env)
    problems: list[Problem] = []
    allow_paid = env.get("SWARM_ALLOW_PAID", "0") == "1"

    # 0. A conflicted worktree poisons every gate and can be committed by the
    #    next green run; stop before the first paid call.
    conflicts = unmerged_paths()
    if conflicts:
        problems.append(
            Problem(
                "worktree",
                "unmerged paths — resolve them or `git merge --abort` before a run: "
                + ", ".join(conflicts[:6]),
            )
        )

    # 1. Model ids present, free-guard, provider key present.
    for var in ROLE_VARS:
        model = env.get(var, "").strip()
        if not model:
            problems.append(Problem(var, "not set (copy .env.example → .env and fill it in)"))
            continue
        if model != env.get(var, ""):
            problems.append(Problem(var, "leading/trailing whitespace in model id"))
        prov = provider(model)
        if not is_free_model(model) and not allow_paid:
            problems.append(
                Problem(var, f"paid model {model} (needs SWARM_ALLOW_PAID=1 + allow_paid)")
            )
        if prov == "openrouter" and not env.get("OPENROUTER_API_KEY"):
            problems.append(Problem(var, "uses OpenRouter but OPENROUTER_API_KEY is empty"))
        if prov == "zen" and not env.get("OPENCODE_API_KEY"):
            problems.append(Problem(var, "uses Zen but OPENCODE_API_KEY is empty"))

    # 2. Local/cloud model availability.
    if not offline:
        ollama_roles = [env.get(v, "").strip() for v in ROLE_VARS if provider(env.get(v, "")) == "ollama"]
        if ollama_roles:
            base = env.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA)
            try:
                have = _available_ollama(base, fetch)
            except Exception as e:  # noqa: BLE001 - report reachability, don't crash
                problems.append(Problem("ollama", f"not reachable at {base}: {e}"))
            else:
                for model in ollama_roles:
                    want = model_id(model).removesuffix(":latest")
                    if want not in have:
                        problems.append(
                            Problem("ollama", f"{model} is not pulled (have: {sorted(have)})")
                        )
        try:
            avail = _ping_model_ids(env, fetch)
        except Exception as e:  # noqa: BLE001
            problems.append(Problem("cloud", f"model list request failed: {e}"))
        else:
            for var in ROLE_VARS:
                model = env.get(var, "").strip()
                prov = provider(model) if model else ""
                if prov in avail and model_id(model) not in avail[prov]:
                    problems.append(
                        Problem(var, f"{model_id(model)} is not offered by {prov} right now")
                    )

    # 3. Venvs + gate binaries (same PATH the Guarded Shell uses).
    for label, path in (
        ("app venv", REPO_ROOT / ".venv" / "bin" / "python"),
        ("swarm venv", REPO_ROOT / "swarm" / ".venv" / "bin" / "python"),
    ):
        if not path.exists():
            hint = "make dev-setup" if label == "app venv" else "make swarm-test"
            problems.append(Problem(label, f"missing {path} (run `{hint}`)"))
    bins = [REPO_ROOT / ".venv" / "bin", REPO_ROOT / "swarm" / ".venv" / "bin"]
    path_env = os.pathsep.join([str(b) for b in bins if b.exists()] + [env.get("PATH", "")])
    for binary in _gate_binaries(env):
        if not which(binary, path=path_env):
            problems.append(Problem("gates", f"`{binary}` not found in the project venvs"))
    return problems


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Validate swarm model/venv configuration.")
    ap.add_argument("--offline", action="store_true", help="skip provider model-list requests")
    args = ap.parse_args()

    from swarm import llms

    for var in ROLE_VARS:
        model = os.getenv(var, "")
        print(f"{var:<24} {model or '<missing>':<58} {provider(model) if model else '-'}")

    # Reuse the factory so a broken factory (not just a broken id) is caught.
    for name, factory in (
        ("planner", llms.planner_llm),
        ("coder", llms.coder_llm),
        ("reviewer", llms.reviewer_llm),
        ("senior", llms.senior_llm),
        ("verifier", llms.verifier_llm),
    ):
        try:
            factory()
        except Exception as e:  # noqa: BLE001
            print(f"factory {name}: FAILED {e}")
            return 1

    problems = check(offline=args.offline)
    for p in problems:
        print(f"FAIL {p}")
    if problems:
        print(f"\n{len(problems)} preflight problem(s) — fix before running the pilot.")
        return 1
    print("\npreflight OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
