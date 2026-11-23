"""Spec acceptance pass (043, harness): the final greenlight.

Every existing guard judges **one task**. Nothing looks at the whole product
after a batch and asks "do the specs still describe working software?". 040
shipped several tasks green while the app could not plan a route and rendered
the walk controls twice.

This module is the end-of-batch pass:

* pick every `specs/product/*` spec that has built work (at least one ticked task);
* serve the local build (fixture backend) and drive it with Playwright;
* check each acceptance criterion (deterministic probes first, a free vision
  model as the second opinion);
* write `<spec>/acceptance.md` and append `T<n>` fix tasks for failing ACs;
* exit non-zero when a requirement failed.

`SWARM_ACCEPT=0` disables the supervisor hook, `SWARM_ACCEPT_VISION=0` skips the
vision call, `SWARM_ACCEPT_QUEUE=0` only reports. The browser runner lives in
`frontend/scripts/acceptance.mjs` so the Python side needs no Playwright.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DISABLE_ENV = "SWARM_ACCEPT"
VISION_ENV = "SWARM_ACCEPT_VISION"
QUEUE_ENV = "SWARM_ACCEPT_QUEUE"
MODEL_ENV = "SWARM_ACCEPT_MODEL"
DEFAULT_VISION_MODEL = "openrouter/nvidia/nemotron-3.5-super-vl:free"
VIEWS = (("desktop", 1280, 800), ("mobile", 390, 844))
CHECK_KINDS = (
    "exists",
    "absent",
    "count",
    "min_count",
    "text",
    "value_set",
    "route_request",
)

_AC_RE = re.compile(r"^\s*[-*]?\s*\*\*(AC-\d+)\s*[—–:-]\s*(.+?)\*\*\s*(.*)$")
_TASK_LINE_RE = re.compile(r"^- \[[ xX]\] (T\d+)\b", re.MULTILINE)
_OPEN_TASK_RE = re.compile(r"^- \[ \] T\d+\b.*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Criterion:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Check:
    """One deterministic browser assertion, declared in `acceptance.toml`."""

    ac: str
    kind: str
    selector: str = ""
    expect: Any = None
    viewport: str = "both"
    value: str = ""
    file: str = ""
    note: str = ""


@dataclass
class SpecReport:
    spec: str
    title: str
    criteria: list[Criterion]
    checks: list[Check]
    ac_verdicts: dict[str, dict[str, str]] = field(default_factory=dict)
    global_failures: list[str] = field(default_factory=list)
    view_facts: dict[str, dict[str, Any]] = field(default_factory=dict)
    vision: dict[str, dict[str, str]] = field(default_factory=dict)
    shots: dict[str, str] = field(default_factory=dict)
    queued: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.global_failures:
            return "FAIL"
        verdicts = [entry.get("verdict") for entry in self.ac_verdicts.values()]
        if "fail" in verdicts:
            return "FAIL"
        if "pass" in verdicts:
            return "PASS"
        return "UNVERIFIED"

    @property
    def counts(self) -> dict[str, int]:
        out = {"pass": 0, "fail": 0, "unverified": 0}
        for entry in self.ac_verdicts.values():
            out[entry.get("verdict", "unverified")] = (
                out.get(entry.get("verdict", "unverified"), 0) + 1
            )
        return out

    @property
    def failures(self) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for ac, entry in self.ac_verdicts.items():
            if entry.get("verdict") != "fail":
                continue
            criterion = next((c for c in self.criteria if c.id == ac), None)
            check = next((c for c in self.checks if c.ac == ac), None)
            out.append(
                {
                    "ac": ac,
                    "title": criterion.title if criterion else "",
                    "evidence": entry.get("evidence", ""),
                    "file": check.file if check else "",
                }
            )
        return out


@dataclass
class AcceptanceRun:
    verdict: str
    reports: list[SpecReport]
    queued: int

    @property
    def exit_code(self) -> int:
        return 1 if self.verdict == "FAIL" else 0


# ---------------------------------------------------------------------------
# parsing + discovery
# ---------------------------------------------------------------------------


def parse_criteria(text: str) -> list[Criterion]:
    """`- **AC-n** — Title. body` paragraphs, continuation lines folded in."""
    out: list[Criterion] = []
    current: Criterion | None = None
    for line in (text or "").splitlines():
        match = _AC_RE.match(line)
        if match:
            if current is not None:
                out.append(current)
            current = Criterion(
                id=match.group(1),
                title=match.group(2).strip().rstrip("."),
                text=match.group(3).strip(),
            )
            continue
        if current is None:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "|", "- **AC-")):
            out.append(current)
            current = None
        else:
            current = Criterion(
                current.id, current.title, f"{current.text} {stripped}".strip()
            )
    if current is not None:
        out.append(current)
    return out


def spec_title(spec_dir: Path) -> str:
    try:
        for line in (spec_dir / "spec.md").read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return spec_dir.name


def built_product_specs(repo: Path | None = None) -> list[Path]:
    """Product specs with at least one ticked task (harness specs never)."""
    from swarm.spec_loader import iter_spec_dirs, spec_kind

    root = Path(repo or REPO_ROOT)
    out: list[Path] = []
    for path in iter_spec_dirs(root):
        if spec_kind(root, path.name) != "product":
            continue
        try:
            text = (path / "tasks.md").read_text()
        except OSError:
            continue
        if re.search(r"^- \[[xX]\] T\d+", text, re.MULTILINE):
            out.append(path)
    return out


def load_checks(spec_dir: Path) -> list[Check]:
    """Optional `<spec>/acceptance.toml`; an empty file means generic checks only."""
    path = spec_dir / "acceptance.toml"
    if not path.exists():
        return []
    try:
        import tomllib

        data = tomllib.loads(path.read_text())
    except (OSError, ValueError):
        return []
    checks: list[Check] = []
    for raw in data.get("check", []) or []:
        if not isinstance(raw, Mapping):
            continue
        kind = str(raw.get("kind", "exists")).strip()
        if kind not in CHECK_KINDS:
            continue
        checks.append(
            Check(
                ac=str(raw.get("ac", "")).strip(),
                kind=kind,
                selector=str(raw.get("selector", "")).strip(),
                expect=raw.get("expect"),
                viewport=str(raw.get("viewport", "both")).strip() or "both",
                value=str(raw.get("value", "")).strip(),
                file=str(raw.get("file", "")).strip(),
                note=str(raw.get("note", "")).strip(),
            )
        )
    return checks


def load_criteria(spec_dir: Path) -> list[Criterion]:
    try:
        text = (spec_dir / "spec.md").read_text()
    except OSError:
        return []
    return parse_criteria(text)


# ---------------------------------------------------------------------------
# verdict merge
# ---------------------------------------------------------------------------


def _detail(check: Check, result: Mapping[str, Any]) -> str:
    return str(result.get("detail") or check.note or check.kind)


def _vision_verdict(vision: Mapping[str, Any], ac: str) -> tuple[str, str]:
    entry = vision.get(ac) or {}
    verdict = str(entry.get("verdict", "")).strip().lower()
    if verdict not in {"pass", "fail"}:
        return "", str(entry.get("note", "")).strip() or "unclear"
    return verdict, str(entry.get("note", "")).strip()


def merge_ac_verdicts(
    criteria: list[Criterion],
    checks: list[Check],
    browser_checks: list[Mapping[str, Any]],
    vision: Mapping[str, Any],
) -> dict[str, dict[str, str]]:
    """Deterministic probes decide; vision fills ACs with no probe; never guess."""
    results_by_ac: dict[str, list[Mapping[str, Any]]] = {}
    for result in browser_checks:
        results_by_ac.setdefault(str(result.get("ac", "")), []).append(result)

    out: dict[str, dict[str, str]] = {}
    for criterion in criteria:
        results = results_by_ac.get(criterion.id, [])
        declared = [check for check in checks if check.ac == criterion.id]
        if results:
            ok = all(bool(result.get("ok")) for result in results)
            detail = "; ".join(
                _detail(declared[0] if declared else Check("", ""), result)
                for result in results
            )
            out[criterion.id] = {
                "verdict": "pass" if ok else "fail",
                "evidence": detail,
                "source": "probe",
            }
            continue
        verdict, note = _vision_verdict(vision, criterion.id)
        if verdict:
            out[criterion.id] = {
                "verdict": verdict,
                "evidence": note or "vision verdict",
                "source": "vision",
            }
        else:
            out[criterion.id] = {
                "verdict": "unverified",
                "evidence": note or "no acceptance.toml check and no vision verdict",
                "source": "none",
            }
    return out


def evaluate_spec(
    spec_dir: Path,
    *,
    browser: Mapping[str, Any],
    vision: Mapping[str, Any] | None = None,
    shots: Mapping[str, str] | None = None,
) -> SpecReport:
    """Build one spec's verdict from the runner's JSON (no model call here)."""
    spec = spec_dir.name
    criteria = load_criteria(spec_dir)
    checks = load_checks(spec_dir)
    views = browser.get("views") or {}
    results = [
        entry
        for entry in (browser.get("checks") or [])
        if str(entry.get("spec", spec)) == spec
    ]
    report = SpecReport(
        spec=spec,
        title=spec_title(spec_dir),
        criteria=criteria,
        checks=checks,
        view_facts={str(k): dict(v) for k, v in views.items()},
        vision={str(k): dict(v) for k, v in (vision or {}).items()},
        shots={str(k): str(v) for k, v in (shots or {}).items()},
    )
    report.global_failures = global_failures(views)
    report.ac_verdicts = merge_ac_verdicts(criteria, checks, results, report.vision)
    return report


def global_failures(views: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Cheap, model-free facts that must never be ignored when they break."""
    failures: list[str] = []
    for name, facts in views.items():
        errors = [str(e) for e in facts.get("consoleErrors", [])]
        if errors:
            failures.append(f"{name}: console error(s): {'; '.join(errors[:3])}")
        if facts.get("leaflet") and not int(facts.get("tiles") or 0):
            failures.append(f"{name}: the map has 0 tiles (blank map)")
        duplicates = [str(d) for d in facts.get("duplicateButtons", [])]
        if duplicates:
            failures.append(
                f"{name}: duplicate visible controls: {', '.join(duplicates[:5])}"
            )
        if int(facts.get("zeroSize") or 0):
            failures.append(
                f"{name}: {int(facts['zeroSize'])} interactive element(s) with zero size"
            )
        if facts.get("overflow"):
            failures.append(f"{name}: horizontal overflow")
    return failures


# ---------------------------------------------------------------------------
# report + queue
# ---------------------------------------------------------------------------


def render_report(report: SpecReport, *, generated: str | None = None) -> str:
    generated = generated or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts = report.counts
    lines = [
        f"# {report.spec} — Acceptance",
        "",
        (
            f"Generated: {generated} · Verdict: **{report.verdict}** "
            f"({counts['fail']} failed · {counts['pass']} passed · "
            f"{counts['unverified']} unverified)"
        ),
        "",
        "| AC | Verdict | Source | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for ac, entry in report.ac_verdicts.items():
        lines.append(
            f"| {ac} | {entry.get('verdict', 'unverified').upper()} | "
            f"{entry.get('source', 'none')} | {_cell(entry.get('evidence', ''))} |"
        )
    lines += ["", "## Global checks", ""]
    if report.global_failures:
        lines += [f"- **FAIL** {item}" for item in report.global_failures]
    if report.view_facts:
        for name, facts in report.view_facts.items():
            lines.append(
                f"- {name}: tiles={facts.get('tiles', 0)} · "
                f"leaflet={bool(facts.get('leaflet'))} · "
                f"duplicateButtons={facts.get('duplicateButtons') or 'none'} · "
                f"zeroSize={facts.get('zeroSize', 0)} · "
                f"overflow={bool(facts.get('overflow'))} · "
                f"routeRequests={facts.get('routeRequests', 0)}"
            )
    if not report.global_failures and not report.view_facts:
        lines.append("- no browser facts recorded")
    notes = [
        f"- {ac}: {entry.get('verdict')} — {_cell(entry.get('evidence', ''))}"
        for ac, entry in report.vision.items()
        if str(entry.get("verdict", "")).lower() in {"pass", "fail", "unclear"}
    ]
    if notes:
        lines += ["", "## Vision notes (advisory)", "", *notes]
    if report.queued:
        lines += ["", "## Queued fix tasks", "", *[f"- {t}" for t in report.queued]]
    lines.append("")
    return "\n".join(lines)


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip() or "—"


def write_report(spec_dir: Path, report: SpecReport, *, generated: str | None = None) -> Path:
    path = spec_dir / "acceptance.md"
    path.write_text(render_report(report, generated=generated))
    return path


def next_task_id(text: str) -> int:
    ids = [int(m.group(1)[1:]) for m in _TASK_LINE_RE.finditer(text or "")]
    return (max(ids) + 1) if ids else 1


def fix_task_line(failure: Mapping[str, str], *, date: str) -> str:
    ac = str(failure.get("ac", ""))
    title = _cell(str(failure.get("title", ""))).rstrip(".")
    evidence = _cell(str(failure.get("evidence", "")))[:400]
    brief = f"Fix {ac} ({title}): {evidence} (acceptance pass {date})"
    file = str(failure.get("file", "")).strip()
    if file:
        brief += f"; Files: {file}"
    return f"- [ ] T{{id}} ({ac}): {brief}"


def queue_fix_tasks(
    tasks_text: str, failures: list[Mapping[str, str]], *, date: str
) -> tuple[str, list[str]]:
    """Append one unchecked task per failing AC; dedupe open `acceptance` tasks."""
    open_lines = _OPEN_TASK_RE.findall(tasks_text or "")
    next_id = next_task_id(tasks_text or "")
    added: list[str] = []
    for failure in failures:
        ac = str(failure.get("ac", ""))
        already = any(
            f"({ac}" in line and "acceptance" in line.lower() for line in open_lines
        )
        if already:
            continue
        line = fix_task_line(failure, date=date).replace("{id}", str(next_id))
        next_id += 1
        added.append(line)
        open_lines.append(line)
    if not added:
        return tasks_text, []
    text = (tasks_text or "").rstrip("\n")
    return text + "\n" + "\n".join(added) + "\n", added


# ---------------------------------------------------------------------------
# vision (advisory second opinion, free by default)
# ---------------------------------------------------------------------------


def vision_model() -> str:
    return os.getenv(MODEL_ENV, "").strip() or DEFAULT_VISION_MODEL


def _vision_available(model: str) -> bool:
    if model.startswith("openrouter/"):
        return bool(os.getenv("OPENROUTER_API_KEY", "").strip())
    if model.startswith("zen/"):
        return bool(os.getenv("OPENCODE_API_KEY", "").strip())
    if model.startswith("ollama/"):
        return True
    return True


def _vision_prompt(report: SpecReport) -> str:
    criteria = "\n".join(
        f"{c.id} — {c.title}: {c.text[:500]}" for c in report.criteria
    ) or "(no AC headings found)"
    spec_name = spec_title(Path(report.spec)) if report.spec else "this spec"
    return (
        "You are the final visual acceptance reviewer for " + spec_name + ". "
        "You get the spec's acceptance criteria and screenshots of the built app. "
        "Judge each criterion from what is VISIBLE. Reply with "
        "STRICT JSON only, no markdown: "
        '{"AC-1": {"verdict": "pass|fail|unclear", "note": "short evidence"}}. '
        "Use unclear when a screenshot cannot show it (behaviour, permissions). "
        "A layout that is visibly broken (blank map, duplicated controls, missing "
        "inputs) is fail.\n\nACCEPTANCE CRITERIA:\n" + criteria
    )


def judge_vision(
    report: SpecReport,
    *,
    model: str | None = None,
    complete: Callable[..., Any] | None = None,
) -> dict[str, dict[str, str]]:
    """One free vision call per spec; `{}` on any failure (never fails the pass)."""
    if os.getenv(VISION_ENV, "1") == "0":
        return {}
    model = model or vision_model()
    if not _vision_available(model):
        return {}
    images = [path for path in report.shots.values() if Path(path).is_file()]
    if not images:
        return {}
    parts: list[dict[str, Any]] = [{"type": "text", "text": _vision_prompt(report)}]
    for path in images:
        try:
            encoded = base64.b64encode(Path(path).read_bytes()).decode()
        except OSError:
            continue
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            }
        )
    if len(parts) == 1:
        return {}
    if complete is None:
        import litellm

        complete = litellm.completion
    try:
        response = complete(
            model=model,
            messages=[{"role": "user", "content": parts}],
            temperature=0,
            max_tokens=800,
        )
        raw = response.choices[0].message.content
    except Exception:  # noqa: BLE001 — vision must never fail the pass
        return {}
    return parse_vision_json(raw)


def parse_vision_json(raw: Any) -> dict[str, dict[str, str]]:
    text = str(raw or "")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
    except (TypeError, ValueError):
        return {}
    out: dict[str, dict[str, str]] = {}
    for ac, entry in data.items():
        if not isinstance(entry, Mapping) or not re.fullmatch(r"AC-\d+", str(ac)):
            continue
        out[str(ac)] = {
            "verdict": str(entry.get("verdict", "unclear")).lower(),
            "note": str(entry.get("note", "")),
        }
    return out


# ---------------------------------------------------------------------------
# browser runner + local servers
# ---------------------------------------------------------------------------


class BrowserError(RuntimeError):
    pass


def browser_plan(
    specs: list[Path], *, base_url: str, out_dir: Path
) -> dict[str, Any]:
    checks = []
    for spec in specs:
        for check in load_checks(spec):
            checks.append(
                {
                    "spec": spec.name,
                    "ac": check.ac,
                    "kind": check.kind,
                    "selector": check.selector,
                    "expect": check.expect,
                    "viewport": check.viewport,
                    "value": check.value,
                }
            )
    return {
        "baseUrl": base_url,
        "outDir": str(out_dir),
        "views": [
            {"name": name, "width": width, "height": height}
            for name, width, height in VIEWS
        ],
        "checks": checks,
    }


def run_browser(
    plan: Mapping[str, Any],
    *,
    repo: Path | None = None,
    timeout: int = 240,
    node: str = "node",
) -> dict[str, Any]:
    root = Path(repo or REPO_ROOT)
    out_dir = Path(str(plan["outDir"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "plan.json"
    plan_path.write_text(json.dumps(dict(plan), indent=2))
    script = root / "frontend" / "scripts" / "acceptance.mjs"
    if not script.is_file():
        raise BrowserError(f"missing browser runner: {script}")
    proc = subprocess.run(
        [node, str(script), str(plan_path)],
        cwd=root / "frontend",
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise BrowserError(
            f"browser runner failed ({proc.returncode}): "
            f"{(proc.stderr or proc.stdout)[-1200:]}"
        )
    try:
        return json.loads(proc.stdout)
    except ValueError as e:
        raise BrowserError(f"browser runner printed no JSON: {proc.stdout[-800:]}") from e


def _free_port(preferred: int) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return int(sock.getsockname()[1])
    raise OSError("no free port")


def _wait_http(url: str, *, timeout: float, proc: subprocess.Popen | None = None) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(f"server exited early: {url}")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
    raise TimeoutError(f"server did not come up: {url}")


@contextlib.contextmanager
def served_app(
    *,
    repo: Path | None = None,
    build: bool = True,
    log: Callable[[str], None] = print,
) -> Iterator[str]:
    """Serve the local build with the fixture backend; yield the preview URL."""
    root = Path(repo or REPO_ROOT)
    procs: list[subprocess.Popen] = []
    logs: list[Any] = []
    try:
        if build:
            log("acceptance: building frontend")
            built = subprocess.run(
                ["npm", "--prefix", "frontend", "run", "build"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            if built.returncode != 0:
                raise RuntimeError(
                    "frontend build failed: " + (built.stderr or built.stdout)[-1200:]
                )
        backend_port = _free_port(8010)
        preview_port = _free_port(4174)
        env = dict(os.environ)
        env.update(
            {
                "ROUTE_FIXTURES": "1",
                "MAPBOX_TOKEN": env.get("MAPBOX_TOKEN") or "acceptance-fixtures-token",
            }
        )
        log_path = root / "swarm" / "runs" / "acceptance-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = log_path.open("w")
        logs.append(handle)
        python = root / ".venv" / "bin" / "python"
        backend = subprocess.Popen(
            [
                str(python if python.exists() else sys.executable),
                "-m",
                "uvicorn",
                "app.main:app",
                "--port",
                str(backend_port),
            ],
            cwd=root,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
        procs.append(backend)
        _wait_http(f"http://127.0.0.1:{backend_port}/docs", timeout=60, proc=backend)
        preview_env = dict(env)
        preview_env["VITE_BACKEND_URL"] = f"http://127.0.0.1:{backend_port}"
        preview = subprocess.Popen(
            [
                "npm",
                "--prefix",
                "frontend",
                "run",
                "preview",
                "--",
                "--port",
                str(preview_port),
                "--strictPort",
            ],
            cwd=root,
            env=preview_env,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
        procs.append(preview)
        url = f"http://127.0.0.1:{preview_port}/"
        _wait_http(url, timeout=120, proc=preview)
        log(f"acceptance: serving {url} (backend :{backend_port})")
        yield url
    finally:
        for proc in reversed(procs):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        for handle in logs:
            handle.close()


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def run(
    *,
    repo: Path | None = None,
    specs: list[str] | None = None,
    queue: bool = True,
    build: bool = True,
    base_url: str | None = None,
    log: Callable[[str], None] = print,
    browser_runner: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    vision_judge: Callable[[SpecReport], Mapping[str, Any]] | None = None,
) -> AcceptanceRun:
    """Run the pass; never raises for a failing requirement (the verdict says it)."""
    from swarm.spec_loader import resolve_spec_dir

    root = Path(repo or REPO_ROOT)
    if specs:
        chosen = []
        for name in specs:
            path = resolve_spec_dir(root, name)
            if path is not None:
                chosen.append(path)
    else:
        chosen = built_product_specs(root)
    if not chosen:
        return AcceptanceRun("UNVERIFIED", [], 0)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = root / "swarm" / "runs" / "acceptance" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    runner = browser_runner or (lambda plan: run_browser(plan, repo=root))
    reports: list[SpecReport] = []

    with contextlib.ExitStack() as stack:
        url = base_url
        if url is None:
            url = stack.enter_context(served_app(repo=root, build=build, log=log))
        plan = browser_plan(chosen, base_url=url, out_dir=out_dir)
        browser = dict(runner(plan))

    for spec_dir in chosen:
        report = evaluate_spec(
            spec_dir,
            browser=browser,
            shots=browser.get("shots") or {},
        )
        if vision_judge is not None:
            judged = dict(vision_judge(report))
        elif os.getenv(VISION_ENV, "1").lower() != "0":
            judged = judge_vision(report)
        else:
            judged = {}
        if judged:
            report.vision = {str(k): dict(v) for k, v in judged.items()}
            # Re-merge so an AC with no probe gets the vision verdict.
            report.ac_verdicts = merge_ac_verdicts(
                report.criteria,
                report.checks,
                [
                    entry
                    for entry in (browser.get("checks") or [])
                    if str(entry.get("spec", spec_dir.name)) == spec_dir.name
                ],
                report.vision,
            )
        write_report(spec_dir, report)
        if queue and os.getenv(QUEUE_ENV, "1") != "0":
            tasks_path = spec_dir / "tasks.md"
            try:
                text = tasks_path.read_text()
            except OSError:
                text = ""
            date = stamp[:4] + "-" + stamp[4:6] + "-" + stamp[6:8]
            new_text, added = queue_fix_tasks(text, report.failures, date=date)
            if added:
                tasks_path.write_text(new_text)
                report.queued = [line.split(" ", 2)[2][:120] for line in added]
        reports.append(report)
        counts = report.counts
        log(
            f"acceptance: {report.spec} → {report.verdict} "
            f"({counts['fail']} failed, {counts['pass']} passed, "
            f"{counts['unverified']} unverified)"
        )

    verdict = (
        "FAIL" if any(report.verdict == "FAIL" for report in reports) else "PASS"
    )
    if verdict == "PASS" and all(report.verdict == "UNVERIFIED" for report in reports):
        verdict = "UNVERIFIED"
    queued = sum(len(report.queued) for report in reports)
    print(
        f"acceptance: {verdict} · {len(reports)} spec(s) · "
        f"{queued} fix task(s) queued · {out_dir}",
        flush=True,
    )
    return AcceptanceRun(verdict, reports, queued)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spec acceptance pass (043)")
    parser.add_argument("--spec", action="append", default=[], help="spec name/prefix")
    parser.add_argument("--no-vision", action="store_true", help="skip the vision call")
    parser.add_argument("--no-queue", action="store_true", help="do not append fix tasks")
    parser.add_argument("--no-build", action="store_true", help="reuse frontend/dist")
    parser.add_argument("--base-url", default=None, help="use an already-running app")
    args = parser.parse_args(argv)
    if os.getenv(DISABLE_ENV, "1") == "0":
        print("acceptance: disabled by SWARM_ACCEPT=0")
        return 0
    if args.no_vision:
        os.environ[VISION_ENV] = "0"
    result = run(
        specs=args.spec or None,
        queue=not args.no_queue,
        build=not args.no_build,
        base_url=args.base_url,
    )
    return result.exit_code