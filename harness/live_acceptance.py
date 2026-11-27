#!/usr/bin/env python3
"""Opt-in live acceptance lane (Mapbox, Postgres, the Render deployment).

The hermetic gate (`make swarm-accept`) runs the same build with
`ROUTE_FIXTURES=1` and no database. A few ACs cannot be observed there:

* 008 AC-1 — routes come from the real Mapbox provider;
* 004 AC-3 — manual preference persists through the prefs endpoint (Postgres);
* 005 AC-1 — save -> list -> recall -> delete (Postgres);
* 035 AC-1/AC-2 — the public Render deployment serves the app and a route.

Those specs declare a `live.toml` next to `acceptance.toml`. This script runs
them against the real providers/deployment and writes `acceptance-live.md` per
spec. It is never part of `--strict`: it is network- and database-dependent.

    make accept-live                 # everything that is currently possible
    make accept-live ARGS="--spec 008"
    make accept-live ARGS="--spec 035"

The local lane needs `MAPBOX_TOKEN` (the app loads `.env` itself). DB specs are
skipped, not failed, when `DATABASE_URL` is unset (`make swarm-db-up`).
"""

from __future__ import annotations

import argparse
import os
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
from swarm.drivers.acceptance import VIEWS, run_browser, served_app


def _views() -> list[dict[str, Any]]:
    return [
        {"name": name, "width": width, "height": height}
        for name, width, height in VIEWS
    ]


def load_specs(root: Path, pattern: str | None) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for path in sorted((root / "specs" / "product").glob("*/live.toml")):
        if pattern and pattern not in path.parent.name:
            continue
        data = tomllib.loads(path.read_text())
        target = data.get("target", {}) or {}
        checks = data.get("check", []) or []
        if not checks:
            continue
        specs.append(
            {
                "spec": path.parent.name,
                "target": target,
                "checks": checks,
            }
        )
    return specs


def plan_for(
    specs: list[dict[str, Any]], *, base_url: str, out_dir: Path
) -> dict[str, Any]:
    checks = []
    for spec in specs:
        for raw in spec["checks"]:
            checks.append(
                {
                    "spec": spec["spec"],
                    "ac": str(raw.get("ac", "")).strip(),
                    "kind": str(raw.get("kind", "exists")).strip(),
                    "selector": str(raw.get("selector", "")).strip(),
                    "expect": raw.get("expect"),
                    "viewport": str(raw.get("viewport", "both")).strip() or "both",
                    "value": str(raw.get("value", "")).strip(),
                    "origin": str(raw.get("origin", "")).strip(),
                    "url": str(raw.get("url", "")).strip(),
                }
            )
    return {
        "baseUrl": base_url,
        "outDir": str(out_dir),
        "views": _views(),
        "checks": checks,
        "selftest": False,
        "layout": [],
    }


def verdicts_for(spec: str, results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_ac: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        if result.get("spec") != spec:
            continue
        by_ac.setdefault(str(result.get("ac", "")), []).append(result)
    out: dict[str, dict[str, Any]] = {}
    for ac, checks in by_ac.items():
        passed = all(bool(c.get("ok")) for c in checks)
        evidence = "; ".join(
            f"{c.get('kind')}: {c.get('detail', '')}" for c in checks
        )
        out[ac] = {"verdict": "PASS" if passed else "FAIL", "evidence": evidence}
    return out


def render_report(
    spec: str,
    target: dict[str, Any],
    verdicts: dict[str, dict[str, Any]],
    *,
    stamp: str,
    note: str = "",
    database: bool = False,
) -> str:
    kind = str(target.get("kind", "local"))
    where = (
        "local stand, real providers (fixtures off)"
        if kind == "local"
        else str(target.get("url", "remote"))
    )
    lines = [
        f"# {spec} — Live acceptance",
        "",
        (
            f"Generated: {stamp} · Target: {where} · Database: "
            f"{'used' if database else ('not needed' if not target.get('requires_db') else 'MISSING')}"
        ),
        "",
    ]
    if note:
        lines += [f"> {note}", ""]
    lines += ["| AC | Verdict | Evidence |", "| --- | --- | --- |"]
    for ac, entry in verdicts.items():
        lines.append(
            f"| {ac} | {entry['verdict']} | {entry['evidence'].replace('|', '\\|')[:600]} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(spec: str, text: str) -> Path:
    path = REPO / "specs" / "product" / spec / "acceptance-live.md"
    path.write_text(text)
    return path


def run_plan(
    specs: list[dict[str, Any]], *, base_url: str, out_dir: Path
) -> list[dict[str, Any]]:
    plan = plan_for(specs, base_url=base_url, out_dir=out_dir)
    result = run_browser(plan, repo=REPO, timeout=1800)
    return list(result.get("checks") or [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default="", help="substring filter (e.g. 008)")
    args = parser.parse_args(argv)

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_dir = REPO / "harness" / "runs" / "live" / stamp.replace(":", "").replace("-", "")
    run_dir.mkdir(parents=True, exist_ok=True)

    specs = load_specs(REPO, args.spec or None)
    if not specs:
        print("accept-live: no live.toml matched")
        return 0

    has_db = bool((os.environ.get("DATABASE_URL") or "").strip())
    local, remote, skipped = [], [], []
    for spec in specs:
        target = spec["target"]
        if target.get("kind") == "remote":
            remote.append(spec)
        elif target.get("requires_db") and not has_db:
            skipped.append(spec)
        else:
            local.append(spec)

    results: list[dict[str, Any]] = []
    try:
        if local:
            with served_app(repo=REPO, build=True, fixtures=False) as url:
                print(f"accept-live: local stand {url} (fixtures off)")
                results += run_plan(local, base_url=url, out_dir=run_dir)
        for spec in remote:
            url = str(spec["target"].get("url", "")).strip()
            if not url:
                skipped.append(spec)
                continue
            print(f"accept-live: remote {url}")
            results += run_plan([spec], base_url=url, out_dir=run_dir / spec["spec"])
    except Exception as exc:  # noqa: BLE001 - a dead provider/stand is a report, not a crash
        print(f"accept-live: FAILED — {type(exc).__name__}: {exc}")
        return 1

    failed = 0
    written = []
    for spec in local + remote:
        name = spec["spec"]
        verdicts = verdicts_for(name, results)
        if not verdicts:
            print(f"accept-live: {name} — no results (skipped)")
            continue
        text = render_report(
            name,
            spec["target"],
            verdicts,
            stamp=stamp,
            database=has_db,
        )
        written.append(write_report(name, text))
        bad = [ac for ac, entry in verdicts.items() if entry["verdict"] != "PASS"]
        failed += len(bad)
        status = "PASS" if not bad else f"FAIL ({', '.join(bad)})"
        print(f"accept-live: {name} → {status}")

    for spec in skipped:
        name = spec["spec"]
        text = render_report(
            name,
            spec["target"],
            {},
            stamp=stamp,
            note="SKIPPED: requires DATABASE_URL (run `make swarm-db-up` first).",
            database=False,
        )
        written.append(write_report(name, text))
        print(f"accept-live: {name} → SKIPPED (no DATABASE_URL)")

    print(f"accept-live: reports → {', '.join(str(p) for p in written)}")
    print(f"accept-live: {failed} failed AC(s) · {run_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
