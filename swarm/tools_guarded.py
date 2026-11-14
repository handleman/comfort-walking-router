"""Guarded agent tools (009 T4, 012 AC-2/AC-3): scope-aware writes + argv-only shell."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from crewai.tools import BaseTool
from crewai_tools import FileReadTool
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent

# Small models lose the plot when tool outputs flood context (819k-token blowup
# on Qwen-9B, 2026-10-10). Hard cap every tool observation.
MAX_OBSERVATION = 3000


def coder_read_chars() -> int:
    """Coder observation cap (020 AC-5): `SWARM_CODER_READ_CHARS`, default 3000.

    The verifier keeps its own much larger cap (`FullFileReadTool`); this knob
    only widens what a coder can see in one read when a task needs it.
    """
    try:
        return max(500, int(os.getenv("SWARM_CODER_READ_CHARS", str(MAX_OBSERVATION))))
    except (TypeError, ValueError):
        return MAX_OBSERVATION


def verify_read_chars() -> int:
    """Whole-file read cap for the scenario verifier (019 AC-3).

    Kept in `swarm.verify` (with `SWARM_VERIFY_READ_CHARS`) so the verifier's
    prompt size and its read cap share one knob; imported lazily to keep this
    module free of a module-level cycle.
    """
    from swarm.verify import read_chars

    return read_chars()

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


def task_scope(base: tuple[str, ...], brief: str) -> tuple[str, ...]:
    """The base scope plus the files the task brief itself names.

    DEFAULT_SCOPE covers code, not documentation: a docs-only task (an ADR, a
    README section) could never write its own deliverable, so two 014-T10 runs
    ended with an empty delta while the verifier correctly blocked. The brief's
    own paths are the smallest honest widening — the task already declares them.
    """
    from swarm.prompts import brief_paths

    extra = [path for path in brief_paths(brief) if not in_scope(path, base)]
    return tuple(base) + tuple(extra)


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
            # `-uall`: untracked directories expand to files, so their content is
            # hashed (015 AC-2 evidence freshness depends on this).
            ["git", "status", "--short", "--untracked-files=all"],
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
        if path.is_dir():
            # Defensive: a directory digest covers its files, sorted by path.
            h = hashlib.sha1()
            for child in sorted(p for p in path.rglob("*") if p.is_file()):
                h.update(str(child).encode())
                h.update(child.read_bytes())
            return h.hexdigest()
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
    """FileReadTool with truncated observations + path/secret guard.

    014-T1 (2026-11-12) burned three fix rounds on one assertion: the coder
    asked for `start_line=1, line_count=500` of a 178-line file seven times
    and got the same first 3000 characters every time. The old note ("re-read
    with start_line/line_count") did not say *where* to resume, so the model
    re-read from line 1, got the same head of the file, and changed nothing —
    the run ended `no_progress` with the real defect still there.

    The note now names the exact next line, so a truncated read is a step
    forward instead of a loop. The coder keeps this cap; the scenario verifier
    (019) uses `FullFileReadTool`, whose cap is much larger.
    """

    # Instance, not a constant: `FullFileReadTool` raises it (019 AC-3) without
    # forking the path/secret guard or the resume hint.
    max_observation: int = MAX_OBSERVATION
    # True for the coder read (020 AC-5 reads `SWARM_CODER_READ_CHARS` at call
    # time); the verifier's whole-file read sets it False.
    env_cap: bool = True

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
        start_line = kwargs.get("start_line")
        if start_line is None and len(args) > 1:
            start_line = args[1]
        try:
            start_line = int(start_line or 1)
        except (TypeError, ValueError):
            start_line = 1
        out = super()._run(*args, **kwargs)
        cap = coder_read_chars() if self.env_cap else int(self.max_observation)
        if len(out) > cap:
            return self._truncate(out, start_line, cap, target)
        return out

    def _truncate(self, out: str, start_line: int, cap: int, target: Path) -> str:
        """Head + a note naming the exact line to continue from."""
        head = out[:cap]
        # The last line fully present in the head: the next read starts there.
        last_line = start_line + head.count("\n")
        return (
            head
            + f"\n…[truncated {len(out) - cap} chars; "
            f"showing lines {start_line}-{last_line}. "
            f"CONTINUE with start_line={last_line + 1} (do not re-read from line {start_line})]"
        )


class FullFileReadTool(TrimmedFileReadTool):
    """The scenario verifier's whole-file read (019 AC-3).

    The coder's 3000-char cap is deliberate — small models lose the plot in a
    flood of context — but it is also why 014-T1 never saw line 169 of a
    178-line file and why nobody could check a whole endpoint or a duplicate
    module. This tool reads the whole file up to `SWARM_VERIFY_READ_CHARS`
    (default 60000). A file that is still larger is reported by name and size
    with the line to continue from; it is never silently returned as a head.
    The path/secret guard is inherited unchanged.
    """

    max_observation: int = 60000  # `verify.DEFAULT_READ_CHARS`; the env wins below
    env_cap: bool = False  # the coder's SWARM_CODER_READ_CHARS does not apply here

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_observation", verify_read_chars())
        super().__init__(*args, **kwargs)

    def _truncate(self, out: str, start_line: int, cap: int, target: Path) -> str:
        try:
            name = target.relative_to(Path(REPO_ROOT).resolve()).as_posix()
        except ValueError:
            name = target.name
        head = out[:cap]
        last_line = start_line + head.count("\n")
        lines = out.count("\n") + 1
        return (
            head
            + f"\n…[NOT READ WHOLE: {name} is {len(out)} chars ({lines} lines) from line "
            f"{start_line}, larger than the {cap}-char whole-file cap. Showing lines "
            f"{start_line}-{last_line}. CONTINUE with start_line={last_line + 1}]"
        )


def _frozen_error(path: str) -> str:
    from swarm import tests_first

    if tests_first.is_frozen(path):
        return f"BLOCKED: {path} is a frozen test written from the acceptance criteria; make it pass, do not edit it"
    return ""


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
    # 021 T4: the Test Author may only edit tests; step crews may not edit frozen
    # tests (the freeze guard applies to both).
    test_only: bool = False

    def _run(self, path: str, oldString: str, newString: str, **kwargs: Any) -> str:
        from swarm import tests_first

        if self.test_only and not tests_first.is_test_path(path):
            return f"BLOCKED: the Test Author writes tests only, not {path}"
        frozen = _frozen_error(path)
        if frozen:
            return frozen
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


class SearchArgs(BaseModel):
    pattern: str = Field(..., description="Python regular expression to search for")
    path: str = Field("", description="Optional repo-relative file or directory to limit the search")


SEARCH_SUFFIXES = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".svelte",
    ".json",
    ".css",
    ".html",
    ".md",
    ".sql",
)
SEARCH_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "runs",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "coverage",
    ".svelte-kit",
}
MAX_SEARCH_FILES = 4000
MAX_SEARCH_LINE = 400


class SearchTool(BaseTool):
    """Find a defect without re-reading the same file (020 AC-5).

    014-T1 burned a run re-reading one range because the read cap kept returning
    the same head. A search returns `path:line: text` for a regex, so the coder
    can locate the one line that matters and then read the region it names.
    Read-only: no shell, no writes, no gate. Secret paths and build/vendor
    directories are skipped, and the result set is bounded.
    """

    name: str = "Repo Search"
    description: str = (
        "Search repo files with a regex; returns `path:line: text` (max 40). Read-only."
    )
    args_schema: type[BaseModel] = SearchArgs
    max_results: int = 40

    def _root(self, path: str) -> tuple[Path | None, str]:
        root = Path(REPO_ROOT).resolve()
        target = root if not path.strip() else root / path.strip()
        try:
            resolved = target.resolve()
        except OSError:
            return None, f"BLOCKED: cannot resolve {path!r}"
        if resolved != root and root not in resolved.parents:
            return None, f"BLOCKED: search path outside the repo: {path!r}"
        if is_secret_path(resolved):
            return None, f"BLOCKED: secret path: {path!r}"
        return resolved, ""

    def _run(self, pattern: str, path: str = "", **kwargs: Any) -> str:
        import re as _re

        if not str(pattern or "").strip():
            return "BLOCKED: empty pattern"
        try:
            rx = _re.compile(pattern)
        except _re.error as e:
            return f"BLOCKED: bad regex: {e}"
        root, err = self._root(path)
        if root is None:
            return err
        if root.is_file():
            files = [root] if root.suffix in SEARCH_SUFFIXES else []
        else:
            files = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d.lower() not in SEARCH_SKIP_DIRS]
                for name in filenames:
                    if not name.endswith(SEARCH_SUFFIXES):
                        continue
                    candidate = Path(dirpath) / name
                    if is_secret_path(candidate):
                        continue
                    files.append(candidate)
                    if len(files) >= MAX_SEARCH_FILES:
                        break
                if len(files) >= MAX_SEARCH_FILES:
                    break
        repo = Path(REPO_ROOT).resolve()
        hits: list[str] = []
        for file in sorted(files):
            try:
                text = file.read_text(errors="ignore")
            except (OSError, UnicodeError):
                continue
            try:
                rel = file.relative_to(repo).as_posix()
            except ValueError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if not rx.search(line):
                    continue
                hits.append(f"{rel}:{number}: {line.strip()[:MAX_SEARCH_LINE]}")
                if len(hits) >= self.max_results:
                    return "\n".join(hits) + f"\n…[stopped at {self.max_results} matches]"
        if not hits:
            return f"(no matches for {pattern!r})"
        return "\n".join(hits)

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        return self._run(*args, **kwargs)


class ShellArgs(BaseModel):
    command: str = Field(..., description="Allowlisted shell command")


SHELL_META = set(";&|<>`$()\n\r")
ALLOWED_COMMANDS = {"pytest", "ruff", "mypy", "git", "ls", "cat", "grep", "npm"}
GATE_BINARIES = frozenset({"pytest", "ruff", "mypy"})
# npm scripts that are gates (QA-only). `build` stays available to coders as a
# compile check; `check`/`lint`/`test` are verification, not development.
NPM_GATE_SCRIPTS = frozenset({"check", "lint", "test"})


def _configured_gate(argv: list[str]) -> bool:
    """Exact match against the project's `SWARM_GATE_COMMANDS` entries.

    Lets another project define its own gates (e.g. `make check`) without
    editing this harness, while still refusing arbitrary commands.
    """
    raw = os.getenv("SWARM_GATE_COMMANDS", "").strip()
    if not raw:
        return False
    for command in re.split(r"[;\n]", raw):
        try:
            if shlex.split(command) == argv:
                return True
        except ValueError:
            continue
    return False


def is_gate_command(argv: list[str]) -> bool:
    """True when argv is one of the project's gates (QA-only by policy).

    Covers the classic checkers, the configured `SWARM_GATE_COMMANDS`, and the
    repo's npm verification scripts. Read-only inspection (`git`, `ls`, `cat`,
    `grep`) and `npm --prefix frontend run build` stay available to coders.
    """
    if not argv:
        return False
    if argv[0] in GATE_BINARIES or _configured_gate(argv):
        return True
    if argv[0] != "npm" or not _valid_npm(argv):
        return False
    script = argv[4] if argv[3:4] == ["run"] and len(argv) > 4 else argv[3] if len(argv) > 3 else ""
    return script in NPM_GATE_SCRIPTS


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
    # `format`/`lint:fix` are deterministic, in-scope autofixes (Prettier/ESLint);
    # `install` stays blocked. Gates themselves remain QA-only (see
    # is_gate_command).
    return script in {"check", "build", "lint", "lint:fix", "format"} and argv[5:] == []


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
        "Run allowlisted argv-only commands: the project gate commands from "
        "`SWARM_GATE_COMMANDS` (QA only); `git status|diff|log` (read-only); ls, cat, grep "
        "(read-only inspection); `npm --prefix frontend run check|build|lint|test` for "
        "this repo. 120s timeout, repo cwd. No shell metacharacters, absolute paths, "
        "'..', .env/key files, network, or npm install."
    )
    args_schema: type[BaseModel] = ShellArgs
    timeout: int = 120
    # Coder-side agents get allow_gates=False: QA is the only role that runs the
    # gates, so development tokens are not spent re-running the same commands.
    allow_gates: bool = True
    # Evidence sink (015): every execution is recorded here with the agent role,
    # argv, exit code, and the in-scope hash at execution time.
    run_dir: str = ""
    agent_role: str = ""

    def _evidence(self) -> tuple[Path | None, str]:
        run_dir = self.run_dir or os.getenv("SWARM_RUN_DIR", "")
        if not run_dir:
            return None, self.agent_role
        from swarm.evidence import SHELL_LOG

        return Path(run_dir) / SHELL_LOG, self.agent_role or "coder"

    def _log_execution(self, argv: list[str], exit_code: int, tail: str, started: float) -> None:
        path, role = self._evidence()
        if path is None:
            return
        import time as _time

        from swarm.evidence import append_execution

        changed = hash_paths(in_scope_changes(_git_changed()))
        append_execution(
            path,
            agent=role,
            argv=argv,
            exit_code=exit_code,
            duration_ms=int((_time.monotonic() - started) * 1000),
            changed_after=hashlib.sha256(json.dumps(changed, sort_keys=True).encode()).hexdigest(),
            tail=tail,
        )

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
        if not argv:
            return f"BLOCKED: not allowlisted: {command!r}"
        allowed = (
            argv[0] in ALLOWED_COMMANDS
            and VALIDATORS[argv[0]](argv)
        ) or _configured_gate(argv)
        if not _no_meta(argv) or not allowed:
            return f"BLOCKED: unsafe arguments: {command!r}"
        if not self.allow_gates and is_gate_command(argv):
            return (
                "BLOCKED: gates are QA-only. Do not re-run them; read the gate "
                "transcript in your task and fix its reported failures."
            )
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
            started = time.monotonic()
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
            self._log_execution(argv, 124, "timeout after 120s", time.monotonic())
            return "BLOCKED: timeout after 120s"
        tail = (p.stdout + p.stderr)[-4000:]
        self._log_execution(argv, p.returncode, tail, started)
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
    test_only: bool = False

    def _run(self, path: str, content: str = "", **kwargs: Any) -> str:
        from swarm import tests_first

        if self.test_only and not tests_first.is_test_path(path):
            return f"BLOCKED: the Test Author writes tests only, not {path}"
        frozen = _frozen_error(path)
        if frozen:
            return frozen
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
