"""Guarded agent tools (009 T4, 012 AC-2/AC-3): scope-aware writes + argv-only shell."""

from __future__ import annotations

import hashlib
import os
import posixpath
import shlex
import subprocess
from pathlib import Path
from typing import Any

from crewai.tools import BaseTool
from crewai_tools import FileReadTool
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent

# Small models lose the plot when tool outputs flood context (819k-token blowup
# on Qwen-9B, 2026-10-10). Hard cap every tool observation.
MAX_OBSERVATION = 3000

# Coder scope: only these repo-relative prefixes/files may change (SWARM_SCOPE
# overrides, comma-separated). Everything else (swarm/, specs/, docs/, .env*) is
# off-limits. Keep this the single source of truth: crew.py derives its prompt
# from it, and flow.py resolves the same override.
DEFAULT_SCOPE = (
    "app/",
    "frontend/",
    "tests/",
    "contracts/",
    "requirements-dev.txt",
    "requirements.txt",
    "pyproject.toml",
    ".gitignore",
)

SECRET_NAMES = {"id_rsa", "id_ed25519", "credentials", "credentials.json", "secrets", "secrets.json"}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def is_secret_path(path: str | Path) -> bool:
    """True for env files, private keys, credential stores, and .git internals."""
    p = Path(str(path))
    name = p.name.lower()
    if any(part.lower() == ".git" for part in p.parts):
        return True
    if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
        return True
    if name in SECRET_NAMES:
        return True
    return name.endswith(SECRET_SUFFIXES)


def _safe_rel(path: str) -> str | None:
    """Normalize a repo-relative path; None when absolute, escaping, or secret."""
    raw = str(path).strip()
    if not raw or "\x00" in raw or raw.startswith("~"):
        return None
    if Path(raw).is_absolute():
        return None
    slashed = raw.replace("\\", "/")
    if ".." in slashed.split("/"):
        return None
    norm = posixpath.normpath(slashed)
    if norm in ("", ".", "..") or norm.startswith(("../", "/")):
        return None
    if is_secret_path(norm):
        return None
    return norm


def resolve_scope() -> tuple[str, ...]:
    """Coder scope: SWARM_SCOPE (comma-separated) overrides, else DEFAULT_SCOPE."""
    return tuple(s for s in os.getenv("SWARM_SCOPE", "").split(",") if s) or DEFAULT_SCOPE


def in_scope(path: str, scope: tuple[str, ...] | None = None) -> bool:
    """True when `path` is inside an allowed directory prefix or exact file."""
    norm = _safe_rel(path)
    if norm is None:
        return False
    for entry in scope or resolve_scope():
        e = entry.replace("\\", "/")
        if e.endswith("/"):
            if norm.startswith(e):
                return True
        elif norm == e or norm.startswith(e + "/"):
            return True
    return False


def scope_violations(changed: list[str], scope: tuple[str, ...] | None = None) -> list[str]:
    return [p for p in changed if not in_scope(p, scope) or is_secret_path(p)]


def _git_changed() -> list[str]:
    try:
        p = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return [line[3:].strip().strip('"').split(" -> ")[-1] for line in p.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        return []


def _digest(path: Path) -> str | None:
    try:
        return hashlib.sha1(path.read_bytes()).hexdigest()
    except OSError:
        return None


def snapshot_worktree() -> dict[str, str]:
    """Hash every currently dirty/untracked path. Baseline for run attribution.

    ``<missing>`` distinguishes a deletion from a path that was never dirty.
    """
    out: dict[str, str] = {}
    for p in _git_changed():
        digest = _digest(Path(REPO_ROOT) / p)
        out[p] = digest if digest is not None else "<missing>"
    return out


def run_delta(baseline: dict[str, str]) -> list[str]:
    """Paths whose content changed since `baseline` (new + modified + deleted)."""
    current = snapshot_worktree()
    return sorted(p for p in set(baseline) | set(current) if baseline.get(p) != current.get(p))


def hash_paths(paths: list[str]) -> dict[str, str]:
    """Content hash per path; `<missing>` marks a deleted/not-yet-created path."""
    out: dict[str, str] = {}
    for p in paths:
        digest = _digest(Path(REPO_ROOT) / p)
        out[p] = digest if digest is not None else "<missing>"
    return out


def in_scope_changes(changed: list[str], scope: tuple[str, ...] | None = None) -> list[str]:
    """Run-delta subset that the coder is allowed to own."""
    return [p for p in changed if in_scope(p, scope) and not is_secret_path(p)]


def _read_target(file_path: str, base_dir: str | Path | None = None) -> Path | None:
    """Resolve a readable target inside the repo (or an explicit base_dir)."""
    raw = str(file_path).strip()
    if not raw or "\x00" in raw:
        return None
    roots = [Path(REPO_ROOT).resolve()]
    if base_dir:
        roots.append(Path(base_dir).resolve())
    p = Path(raw)
    if p.is_absolute():
        target = p.resolve()
    else:
        rel = _safe_rel(raw)
        if rel is None:
            return None
        root = Path(base_dir).resolve() if base_dir else Path(REPO_ROOT).resolve()
        target = (root / rel).resolve()
        if target != root and root not in target.parents:
            return None
    if not any(target == r or r in target.parents for r in roots):
        return None
    if is_secret_path(target):
        return None
    return target


class TrimmedFileReadTool(FileReadTool):
    """FileReadTool with truncated observations + path/secret guard."""

    def _run(self, *args: Any, **kwargs: Any) -> str:
        supplied = kwargs.get("file_path")
        if supplied is None and args:
            supplied = args[0]
        if supplied is None:
            supplied = getattr(self, "file_path", None)
        target = _read_target(str(supplied), getattr(self, "base_dir", None))
        if target is None:
            return f"BLOCKED: unsafe or secret read path: {supplied!r}"
        if "file_path" in kwargs or not args:
            kwargs["file_path"] = str(target)
        else:
            args = (str(target), *args[1:])
        out = super()._run(*args, **kwargs)
        if len(out) > MAX_OBSERVATION:
            return out[:MAX_OBSERVATION] + f"\n…[truncated {len(out) - MAX_OBSERVATION} chars; re-read with start_line/line_count]"
        return out


def _write_target(path: str) -> tuple[Path | None, str]:
    """Validate a write path: repo-relative, inside coder scope, no secrets."""
    rel = _safe_rel(path)
    if rel is None:
        return None, f"BLOCKED: unsafe path: {path!r} (absolute, '..', symlink, or secret)"
    if not in_scope(rel):
        return None, f"BLOCKED: {rel} is outside coder scope {resolve_scope()}"
    target = (Path(REPO_ROOT) / rel).resolve()
    root = Path(REPO_ROOT).resolve()
    if target != root and root not in target.parents:
        return None, f"BLOCKED: {path} escapes repo root"
    if is_secret_path(target):
        return None, f"BLOCKED: {path} is a secret-looking path"
    return target, ""


class EditArgs(BaseModel):
    path: str = Field(..., description="Repo-relative file path inside the coder scope")
    oldString: str = Field(..., description="Exact text to find (must occur exactly once)")
    newString: str = Field(..., description="Replacement text")


class EditTool(BaseTool):
    name: str = "Repo Edit"
    description: str = "Replace one exact occurrence of oldString with newString in an in-scope repo-relative file."
    args_schema: type[BaseModel] = EditArgs

    def _run(self, path: str, oldString: str, newString: str, **kwargs: Any) -> str:
        target, err = _write_target(path)
        if target is None:
            return err
        if not target.is_file():
            return f"BLOCKED: {path} does not exist (create via plan step first)"
        text = target.read_text()
        count = text.count(oldString)
        if count != 1:
            return f"BLOCKED: oldString occurs {count}x in {path} (need exactly 1)"
        target.write_text(text.replace(oldString, newString, 1))
        return f"OK: edited {path}"

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        return self._run(*args, **kwargs)


class ShellArgs(BaseModel):
    command: str = Field(..., description="Allowlisted shell command")


SHELL_META = set(";&|<>`$()\n\r")
ALLOWED_COMMANDS = {"pytest", "ruff", "mypy", "git", "ls", "cat", "grep", "npm"}
CAT_FLAGS = {"-n", "-b", "-s", "-E", "-T", "-v"}
GREP_FLAGS = {"-n", "-i", "-w", "-E", "-F", "-c", "-l", "-h", "-s"}
DENY_FLAGS = {"-p", "--rootdir", "--override-ini", "--pyargs", "--no-index", "--output", "--config-file"}


def _safe_path_arg(arg: str, *, allow_dot: bool = False) -> bool:
    if arg == "-":
        return False
    if arg == "." and allow_dot:
        return True
    return _safe_rel(arg) is not None


def _no_meta(argv: list[str]) -> bool:
    return all(not any(ch in token for ch in SHELL_META) for token in argv)


def _valid_pytest(argv: list[str]) -> bool:
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in DENY_FLAGS:
            return False
        if a in ("-k", "-m"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        if not _safe_path_arg(a, allow_dot=True):
            return False
        i += 1
    return True


def _valid_ruff(argv: list[str]) -> bool:
    if len(argv) < 3 or argv[1] != "check":
        return False
    for a in argv[2:]:
        if a.startswith("-"):
            if a in DENY_FLAGS:
                return False
            continue
        if not _safe_path_arg(a, allow_dot=True):
            return False
    return True


def _valid_mypy(argv: list[str]) -> bool:
    for a in argv[1:]:
        if a.startswith("-"):
            if a in DENY_FLAGS:
                return False
            continue
        if not _safe_path_arg(a, allow_dot=True):
            return False
    return True


def _valid_git(argv: list[str]) -> bool:
    if len(argv) < 2 or argv[1] not in {"diff", "status", "log"}:
        return False
    if any(a in DENY_FLAGS for a in argv):
        return False
    for a in argv[2:]:
        if a.startswith("-"):
            continue
        if not _safe_path_arg(a, allow_dot=True):
            return False
    return True


def _valid_ls(argv: list[str]) -> bool:
    for a in argv[1:]:
        if a.startswith("-"):
            continue
        if not _safe_path_arg(a, allow_dot=True):
            return False
    return True


def _valid_cat(argv: list[str]) -> bool:
    paths = 0
    for a in argv[1:]:
        if a in CAT_FLAGS:
            continue
        if a.startswith("-") or not _safe_path_arg(a):
            return False
        paths += 1
    return paths > 0


def _valid_grep(argv: list[str]) -> bool:
    if any(a in {"-r", "-R", "--recursive", "-e", "-f"} for a in argv):
        return False
    pattern = False
    paths = 0
    for a in argv[1:]:
        if a in GREP_FLAGS:
            continue
        if a.startswith("-"):
            return False
        if not pattern:
            pattern = True
            continue
        if not _safe_path_arg(a, allow_dot=True):
            return False
        paths += 1
    return pattern and paths > 0


def _valid_npm(argv: list[str]) -> bool:
    if argv[1:3] != ["--prefix", "frontend"]:
        return False
    if argv[3:4] == ["test"]:
        return argv[4:] == ["--", "--run"]
    if argv[3:4] != ["run"] or len(argv) < 5:
        return False
    script = argv[4]
    if script == "test":
        return argv[5:] == ["--", "--run"]
    return script in {"check", "build"} and argv[5:] == []


VALIDATORS = {
    "pytest": _valid_pytest,
    "ruff": _valid_ruff,
    "mypy": _valid_mypy,
    "git": _valid_git,
    "ls": _valid_ls,
    "cat": _valid_cat,
    "grep": _valid_grep,
    "npm": _valid_npm,
}


class ShellTool(BaseTool):
    name: str = "Guarded Shell"
    description: str = (
        "Run allowlisted argv-only commands: pytest, `ruff check`, mypy (gates); "
        "`git status|diff|log` (read-only); ls, cat, grep (read-only inspection); "
        "`npm --prefix frontend run check|build|test`. 120s timeout, repo cwd. "
        "No shell metacharacters, absolute paths, '..', .env/key files, network, or npm install."
    )
    args_schema: type[BaseModel] = ShellArgs
    timeout: int = 120

    def _run(self, command: str, **kwargs: Any) -> str:
        raw = command.strip()
        if not raw:
            return "BLOCKED: empty command"
        if any(ch in raw for ch in SHELL_META):
            return f"BLOCKED: shell metacharacters are not allowed: {command!r}"
        try:
            argv = shlex.split(raw)
        except ValueError as e:
            return f"BLOCKED: cannot parse command: {e}"
        if not argv or argv[0] not in ALLOWED_COMMANDS:
            return f"BLOCKED: not allowlisted: {command!r}"
        if not _no_meta(argv) or not VALIDATORS[argv[0]](argv):
            return f"BLOCKED: unsafe arguments: {command!r}"
        try:
            env = dict(os.environ)
            # App gates must use the root .venv; fall back to the harness venv.
            bins = [Path(REPO_ROOT) / ".venv" / "bin", Path(REPO_ROOT) / "swarm" / ".venv" / "bin"]
            env["PATH"] = os.pathsep.join(
                [str(b) for b in bins if b.exists()] + [env.get("PATH", "")]
            )
            # `pytest` (script entrypoint) does not add cwd to sys.path the way
            # `python -m pytest` does; make the app package importable for gates.
            env["PYTHONPATH"] = os.pathsep.join(
                [str(REPO_ROOT), env.get("PYTHONPATH", "")]
            )
            p = subprocess.run(
                argv,
                shell=False,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "BLOCKED: timeout after 120s"
        tail = (p.stdout + p.stderr)[-4000:]
        return f"exit={p.returncode}\n{tail}"

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        return self._run(*args, **kwargs)


class CreateArgs(BaseModel):
    path: str = Field(..., description="Repo-relative file path to create (parents made as needed)")
    content: str = Field(default="", description="Initial file content")


class CreateTool(BaseTool):
    name: str = "Repo Create"
    description: str = "Create a new in-scope repo-relative file. Refuses existing, out-of-scope, escaping, or secret paths."
    args_schema: type[BaseModel] = CreateArgs

    def _run(self, path: str, content: str = "", **kwargs: Any) -> str:
        target, err = _write_target(path)
        if target is None:
            return err
        if target.exists():
            return f"BLOCKED: {path} already exists (use Repo Edit)"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"OK: created {path} ({len(content)} chars)"

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        return self._run(*args, **kwargs)
