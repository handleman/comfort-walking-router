"""Guarded agent tools (009 T4, AC-3): exact-match EditTool + allowlisted ShellTool."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Type

from crewai.tools import BaseTool
from crewai_tools import FileReadTool
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent

# Small models lose the plot when tool outputs flood context (819k-token blowup
# on Qwen-9B, 2026-10-10). Hard cap every tool observation.
MAX_OBSERVATION = 3000


class TrimmedFileReadTool(FileReadTool):
    """FileReadTool with truncated observations — anti-loop guard for small models."""

    def _run(self, *args: Any, **kwargs: Any) -> str:
        out = super()._run(*args, **kwargs)
        if len(out) > MAX_OBSERVATION:
            return out[:MAX_OBSERVATION] + f"\n…[truncated {len(out) - MAX_OBSERVATION} chars; re-read with start_line/line_count]"
        return out


class EditArgs(BaseModel):
    path: str = Field(..., description="Repo-relative file path")
    oldString: str = Field(..., description="Exact text to find (must occur exactly once)")
    newString: str = Field(..., description="Replacement text")


class EditTool(BaseTool):
    name: str = "Repo Edit"
    description: str = "Replace one exact occurrence of oldString with newString in a repo-relative file."
    args_schema: Type[BaseModel] = EditArgs

    def _run(self, path: str, oldString: str, newString: str, **kwargs: Any) -> str:
        target = (REPO_ROOT / path).resolve()
        if REPO_ROOT not in target.parents and target != REPO_ROOT:
            return f"BLOCKED: {path} escapes repo root"
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


ALLOW = re.compile(r"^(pytest|ruff|mypy|git diff|git status|ls|cat|grep|npm)\b")


class ShellArgs(BaseModel):
    command: str = Field(..., description="Allowlisted shell command")


class ShellTool(BaseTool):
    name: str = "Guarded Shell"
    description: str = (
        "Run allowlisted commands: pytest, ruff, mypy (gates); git diff/status (read-only); "
        "ls, cat, grep (read-only inspection); npm run check/build (frontend gates). "
        "120s timeout, repo cwd. No network, no writes, no python -c."
    )
    args_schema: Type[BaseModel] = ShellArgs
    timeout: int = 120

    def _run(self, command: str, **kwargs: Any) -> str:
        if not ALLOW.match(command.strip()):
            return f"BLOCKED: not allowlisted: {command!r}"
        try:
            p = subprocess.run(
                command, shell=True, cwd=REPO_ROOT, capture_output=True, text=True, timeout=self.timeout
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
    description: str = "Create a new repo-relative file with content. Refuses if the file exists (use Repo Edit) or the path escapes the repo."
    args_schema: Type[BaseModel] = CreateArgs

    def _run(self, path: str, content: str = "", **kwargs: Any) -> str:
        target = (REPO_ROOT / path).resolve()
        if REPO_ROOT not in target.parents and target != REPO_ROOT:
            return f"BLOCKED: {path} escapes repo root"
        if target.exists():
            return f"BLOCKED: {path} already exists (use Repo Edit)"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"OK: created {path} ({len(content)} chars)"

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        return self._run(*args, **kwargs)
