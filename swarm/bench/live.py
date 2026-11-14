"""Live replay of one frozen case (020 T7, AC-6).

The offline bench measures prompt text; only a real run shows whether the loop
still reaches green with those prompts. This module makes that replay honest and
disposable:

1. refuse a dirty tree, a linked worktree, or a case without `base_sha`;
2. create a detached worktree at `green_sha^` (the state the task started from);
3. copy the **current** `swarm/` package into it (never the historical one);
4. run one task with pinned models and a scratch run directory, no commit/push;
5. report status, tokens, wall clock, fix rounds and gates; remove the worktree
   on success and keep it (path printed) on failure for inspection.

It is opt-in (`make swarm-bench-live CASE=<id>`) and needs models. Nothing here
runs in `make swarm-test`: the tests cover the guards and the copy filter.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from swarm.bench import corpus

REPO_ROOT = corpus.REPO_ROOT
COPY_IGNORE = {".venv", "venv", "__pycache__", "runs", ".mypy_cache", ".ruff_cache", ".pytest_cache",
               "swarm.egg-info", "bench/corpus"}
DEFAULT_TIMEOUT_SECONDS = 2400


def timeout_seconds(env: dict[str, str] | None = None) -> int:
    """Per-case live-replay timeout (`SWARM_REPLAY_TIMEOUT`, default 2400s)."""
    import os

    source = os.environ if env is None else env
    try:
        return max(120, int(source.get("SWARM_REPLAY_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS


def _git(repo: Path, *args: str) -> tuple[int, str]:
    return corpus.git(repo, *args)


def preflight(repo: Path) -> str | None:
    """Return the reason a live replay must not run, or None."""
    rc, status = _git(repo, "status", "--porcelain")
    if rc != 0:
        return "not a git repository"
    if status.strip():
        return "dirty tree: commit or stash before a live replay"
    rc, git_dir = _git(repo, "rev-parse", "--git-dir")
    rc2, common = _git(repo, "rev-parse", "--git-common-dir")
    if rc == 0 and rc2 == 0 and Path(git_dir.strip()).resolve() != Path(common.strip()).resolve():
        return "this is a linked worktree; run the replay from the primary checkout"
    return None


def bench_models(env: dict[str, str] | None = None) -> dict[str, str]:
    """`SWARM_BENCH_MODELS=coder=...,qa=...,planner=...,senior=...,verifier=...`."""
    source = os.environ if env is None else env
    raw = str(source.get("SWARM_BENCH_MODELS", "")).strip()
    out: dict[str, str] = {}
    for part in raw.replace("\n", ",").split(","):
        if "=" not in part:
            continue
        role, _, model = part.partition("=")
        role, model = role.strip().lower(), model.strip()
        if role and model:
            out[role] = model
    return out


ROLE_ENV = {
    "planner": "SWARM_PLANNER_MODEL",
    "coder": "SWARM_CODER_MODEL",
    "qa": "SWARM_REVIEWER_MODEL",
    "reviewer": "SWARM_REVIEWER_MODEL",
    "senior": "SWARM_SENIOR_MODEL",
    "verifier": "SWARM_VERIFIER_MODEL",
}


def fill_from_dotenv(repo: Path, env: dict[str, str]) -> list[str]:
    """Fill *missing* env vars from the repo's `.env` (models, keys, base URLs).

    A replay must run with the operator's real configuration — the key that
    makes the OpenRouter planner work, the local Ollama URL — but it must not
    override an explicit pin. Values are copied into the child environment
    only; nothing is printed and nothing is written into the worktree.
    """
    from dotenv import dotenv_values

    try:
        values = dotenv_values(repo / ".env")
    except (OSError, ValueError):
        return []
    filled: list[str] = []
    for key, value in values.items():
        if not key or value is None or key in env or value == "":
            continue
        env[key] = value
        filled.append(key)
    return filled


def model_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """The env overrides for pinned models (empty when unpinned)."""
    out: dict[str, str] = {}
    for role, model in bench_models(env).items():
        key = ROLE_ENV.get(role)
        if key:
            out[key] = model
    return out


def copy_harness(repo: Path, destination: Path) -> list[str]:
    """Copy the current `swarm/` package into the worktree; return skipped paths."""
    source = repo / "swarm"
    skipped: list[str] = []
    for dirpath, dirnames, filenames in os.walk(source):
        rel = Path(dirpath).relative_to(source)
        keep: list[str] = []
        for name in dirnames:
            rel_name = (rel / name).as_posix()
            if name in COPY_IGNORE or rel_name in COPY_IGNORE:
                skipped.append(rel_name)
                continue
            keep.append(name)
        dirnames[:] = keep
        target_dir = destination / "swarm" / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            shutil.copy2(Path(dirpath) / name, target_dir / name)
    return skipped


VENV_LINKS = ((".venv", ".venv"), ("swarm/.venv", "swarm/.venv"), ("frontend/node_modules", "frontend/node_modules"))


def link_venvs(repo: Path, worktree: Path) -> list[str]:
    """Reuse the repo's dependency trees instead of bootstrapping in the worktree.

    The harness copy runs with `PYTHONPATH=<worktree>`, so `import swarm` is the
    worktree's code while the interpreters, pytest/mypy/ruff and node_modules are
    the repo's. Bootstrap would take minutes and would use the *worktree* source.
    """
    linked: list[str] = []
    for rel, target_rel in VENV_LINKS:
        target = repo / target_rel
        link = worktree / rel
        if not target.exists() or link.exists():
            continue
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target, target_is_directory=True)
        linked.append(rel)
    return linked


def _last_phase(worktree: Path) -> dict[str, Any]:
    """The last completed/observed phase from a killed run's event stream."""
    from swarm import phases

    run_dir = _run_dir(worktree)
    if run_dir is None:
        return {}
    events: list[dict[str, Any]] = []
    try:
        for line in (Path(run_dir) / "events.jsonl").read_text().splitlines():
            if line.strip():
                events.append(json.loads(line))
    except (OSError, ValueError):
        return {}
    derived = phases.derive(events)
    return derived[-1] if derived else {}


def _run_dir(worktree: Path) -> Path | None:
    latest = worktree / "swarm" / "runs" / "latest"
    try:
        name = latest.read_text().strip()
    except OSError:
        return None
    return worktree / "swarm" / "runs" / name if name else None


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get("usage") or {}
    return {
        "status": payload.get("status"),
        "reason_code": payload.get("reason_code"),
        "fix_rounds": int(payload.get("fix_rounds") or 0),
        "duration_seconds": int(usage.get("duration_seconds") or 0),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "cached_prompt_tokens": int(usage.get("cached_prompt_tokens") or 0),
        "cost_usd": float(payload.get("cost") or 0.0),
        "gates": payload.get("gates") or {},
        "changed_files": payload.get("changed_files") or [],
    }


def run_case(
    case_id: str,
    *,
    repo: Path = REPO_ROOT,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    keep_on_success: bool = False,
    keep_on_failure: bool = True,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run one corpus case end to end in a throwaway worktree."""
    cases = corpus.load_corpus(repo)
    match = [case for case in cases if case.get("id") == case_id]
    if not match:
        return {"ok": False, "error": f"unknown case: {case_id}", "case": case_id}
    case = match[0]
    reason = preflight(repo)
    if reason:
        return {"ok": False, "error": reason, "case": case_id}
    if not case.get("base_sha"):
        return {"ok": False, "error": "case has no base_sha", "case": case_id}

    worktree = Path(tempfile.mkdtemp(prefix=f"swarm-bench-{case_id}-"))
    added = False
    env = dict(os.environ)
    env.update(model_env())
    fill_from_dotenv(repo, env)
    if env_overrides:
        env.update(env_overrides)
    env["SWARM_BENCH"] = "1"
    # The worktree carries the current harness copy on top of the base commit,
    # so `git status` is dirty by construction. Run-attribution already ignores
    # that (the baseline is taken after the copy); the stash hygiene would not,
    # and it would park e.g. the node_modules symlink mid-run.
    env["SWARM_STASH_UNRELATED"] = "0"
    env["PYTHONPATH"] = str(worktree)
    # The repo's `.env` is not copied into the worktree (it holds keys). Pin the
    # gate list from the case itself so the replay runs the task's real gates.
    commands = [g for g in (case.get("gates") or {}) if g != "scope"]
    if commands:
        env["SWARM_GATE_COMMANDS"] = ";".join(commands)
    for rel in (".venv", "swarm/.venv"):
        env["PATH"] = f"{repo / rel / 'bin'}:{env.get('PATH', '')}"
    env.pop("SWARM_REQUIRE_APPROVAL", None)
    try:
        rc, out = _git(repo, "worktree", "add", "--detach", str(worktree), case["base_sha"])
        if rc != 0:
            return {"ok": False, "error": f"worktree add failed: {out.strip()}", "case": case_id}
        added = True
        copy_harness(repo, worktree)
        link_venvs(repo, worktree)
        python = repo / "swarm" / ".venv" / "bin" / "python"
        cmd = [
            str(python),
            "-m",
            "swarm.flow",
            "--spec",
            str(case["spec"]),
            "--task",
            str(case["task"]),
            "--no-commit",
            "--no-tui",
        ]
        # Write the child's output to files, not pipes: a leaked gate process
        # can keep a pipe open after the flow exits, and then `communicate`
        # never returns (one replay hung 57 minutes with a 1300 s timeout).
        out_path = worktree / ".swarm-replay.out"
        err_path = worktree / ".swarm-replay.err"
        with out_path.open("w") as out_f, err_path.open("w") as err_f:
            proc = subprocess.run(
                cmd,
                cwd=worktree,
                env=env,
                check=False,
                stdout=out_f,
                stderr=err_f,
                text=True,
                timeout=timeout,
            )
        try:
            stdout_text = out_path.read_text(errors="ignore")
            stderr_text = err_path.read_text(errors="ignore")
        except OSError:
            stdout_text = stderr_text = ""
        run_dir = _run_dir(worktree)
        payload: dict[str, Any] = {}
        if run_dir is not None:
            try:
                payload = json.loads((run_dir / "run.json").read_text())
            except (OSError, json.JSONDecodeError):
                payload = {}
        summary = _summary(payload) if payload else {}
        result: dict[str, Any] = {
            "ok": bool(summary) and summary.get("status") == "green",
            "case": case_id,
            "exit_code": proc.returncode,
            "worktree": str(worktree),
            **summary,
        }
        failed = proc.returncode != 0 or summary.get("status") != "green"
        if summary and (keep_on_success or (failed and keep_on_failure)):
            result["kept"] = True
            result["tail"] = (stdout_text or stderr_text or "")[-4000:]
            added = False  # keep the worktree for inspection
        elif failed:
            result["tail"] = (stdout_text or stderr_text or "")[-4000:]
        return result
    except subprocess.TimeoutExpired:
        # Keep the tree: a timeout is exactly when the run record is needed.
        added = False
        last = _last_phase(worktree)
        return {
            "ok": False,
            "status": "timeout",
            "error": f"timed out after {timeout}s",
            "case": case_id,
            "worktree": str(worktree),
            "kept": True,
            "last_phase": last.get("phase", ""),
            "last_phase_seconds": last.get("duration_seconds", 0),
        }
    finally:
        if added:
            _git(repo, "worktree", "remove", "--force", str(worktree))
            shutil.rmtree(worktree, ignore_errors=True)


def render(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return f"live replay {result.get('case')}: FAILED — {result.get('error') or result.get('status')}"
    return (
        f"live replay {result['case']}: green in {result['duration_seconds']}s, "
        f"{result['prompt_tokens']:,} prompt tokens "
        f"({result['cached_prompt_tokens']:,} cached), ${result['cost_usd']:.4f}, "
        f"{result['fix_rounds']} fix rounds, {len(result.get('gates') or {})} gates"
    )
