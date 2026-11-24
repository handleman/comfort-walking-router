"""052: the layout contract and its deterministic checks.

A `layout.toml` declares **regions** (top-card, map, sidebar, drawer), the
**controls** that must exist (with candidate regions), and per-viewport
expectations. `evaluate` turns a browser-collected facts snapshot into a list of
issues. It is pure: no DOM, no screenshots, no vision — the `.mjs` runner gathers
rects/visibility/overlaps, this module decides.

The IR is source-agnostic on purpose: a future Figma importer writes the same
`layout.toml`, so the checks never change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Region:
    id: str
    selector: str
    anchor: str = ""
    ac: str = "AC-L"


@dataclass(frozen=True)
class Control:
    id: str
    selector: str
    regions: tuple[str, ...] = ()
    unique: bool = False
    ac: str = "AC-L"
    viewports: tuple[str, ...] = ()  # empty = every viewport


@dataclass(frozen=True)
class ViewportExpect:
    name: str
    visible_regions: tuple[str, ...] = ()
    hidden_regions: tuple[str, ...] = ()
    above: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Tolerance:
    px: float = 2.0
    overlap: float = 0.0


@dataclass(frozen=True)
class LayoutContract:
    regions: dict[str, Region] = field(default_factory=dict)
    controls: dict[str, Control] = field(default_factory=dict)
    expect: dict[str, ViewportExpect] = field(default_factory=dict)
    tolerance: Tolerance = field(default_factory=Tolerance)


@dataclass(frozen=True)
class LayoutIssue:
    check: str
    target: str
    detail: str
    ac: str = "AC-L"


def load_layout(path: Path) -> LayoutContract:
    """Parse a `layout.toml`; raises on malformed input (the caller reports it)."""
    import tomllib

    data = tomllib.loads(Path(path).read_text())
    regions = {
        key: Region(
            id=key,
            selector=str(val.get("selector", "")),
            anchor=str(val.get("anchor", "")),
            ac=str(val.get("ac", "AC-L")),
        )
        for key, val in (data.get("region") or {}).items()
    }
    controls = {
        key: Control(
            id=key,
            selector=str(val.get("selector", "")),
            regions=tuple(val.get("regions") or ()),
            unique=bool(val.get("unique", False)),
            ac=str(val.get("ac", "AC-L")),
            viewports=tuple(val.get("viewports") or ()),
        )
        for key, val in (data.get("control") or {}).items()
    }
    expect = {
        key: ViewportExpect(
            name=key,
            visible_regions=tuple(val.get("visible_regions") or ()),
            hidden_regions=tuple(val.get("hidden_regions") or ()),
            above=tuple(tuple(pair) for pair in (val.get("above") or ())),
        )
        for key, val in (data.get("expect") or {}).items()
    }
    tol = data.get("tolerance") or {}
    tolerance = Tolerance(
        px=float(tol.get("px", 2.0) or 2.0),
        overlap=float(tol.get("overlap", 0.0) or 0.0),
    )
    return LayoutContract(regions=regions, controls=controls, expect=expect, tolerance=tolerance)


def _inside(rect: Mapping[str, Any], region: Mapping[str, Any], tol: float) -> bool:
    if not region or not region.get("visible"):
        return False
    return (
        float(rect.get("x", 0)) >= float(region.get("x", 0)) - tol
        and float(rect.get("y", 0)) >= float(region.get("y", 0)) - tol
        and float(rect.get("x", 0)) + float(rect.get("w", 0))
        <= float(region.get("x", 0)) + float(region.get("w", 0)) + tol
        and float(rect.get("y", 0)) + float(rect.get("h", 0))
        <= float(region.get("y", 0)) + float(region.get("h", 0)) + tol
    )


def evaluate(contract: LayoutContract, facts: Mapping[str, Any]) -> list[LayoutIssue]:
    """Check one facts snapshot (`{"desktop": {...}, "mobile": {...}}`)."""
    issues: list[LayoutIssue] = []
    for name, expect in contract.expect.items():
        view = (facts or {}).get(name)
        if not isinstance(view, Mapping):
            issues.append(LayoutIssue("viewport", name, f"no layout facts for {name}"))
            continue
        regions = view.get("regions") or {}
        controls = view.get("controls") or {}
        for rid in expect.visible_regions:
            if not (regions.get(rid) or {}).get("visible"):
                ac = (contract.regions.get(rid) or Region(id=rid, selector="")).ac
                issues.append(LayoutIssue("region_visible", rid, f"{name}: region {rid} must be visible", ac))
        for rid in expect.hidden_regions:
            if (regions.get(rid) or {}).get("visible"):
                ac = (contract.regions.get(rid) or Region(id=rid, selector="")).ac
                issues.append(LayoutIssue("region_hidden", rid, f"{name}: region {rid} must be hidden", ac))
        for cid, control in contract.controls.items():
            if control.viewports and name not in control.viewports:
                continue
            rect = controls.get(cid)
            if not isinstance(rect, Mapping) or not rect.get("visible"):
                issues.append(LayoutIssue("present", cid, f"{name}: control {cid} missing or invisible", control.ac))
                continue
            if control.unique and int(rect.get("count", 1) or 0) != 1:
                issues.append(
                    LayoutIssue("unique", cid, f"{name}: control {cid} matched {rect.get('count')} times", control.ac)
                )
            if control.regions:
                inside = any(_inside(rect, regions.get(rid) or {}, contract.tolerance.px) for rid in control.regions)
                if not inside:
                    issues.append(
                        LayoutIssue(
                            "in_region",
                            cid,
                            f"{name}: control {cid} is outside {list(control.regions)}",
                            control.ac,
                        )
                    )
        for upper, lower in expect.above:
            u = regions.get(upper) or {}
            lo = regions.get(lower) or {}
            if not u.get("visible") or not lo.get("visible"):
                issues.append(
                    LayoutIssue(
                        "region_order",
                        f"{upper}>{lower}",
                        f"{name}: {upper}/{lower} not both visible for ordering",
                        (contract.regions.get(upper) or Region(id=upper, selector="")).ac,
                    )
                )
            elif float(u.get("y", 0)) + float(u.get("h", 0)) > float(lo.get("y", 0)) + contract.tolerance.px:
                issues.append(
                    LayoutIssue(
                        "region_order",
                        f"{upper}>{lower}",
                        f"{name}: {upper} is not above {lower}",
                        (contract.regions.get(upper) or Region(id=upper, selector="")).ac,
                    )
                )
        for pair in view.get("overlaps") or []:
            a, _, b = str(pair).partition("~")
            issues.append(LayoutIssue("no_overlap", f"{a}~{b}", f"{name}: {a} overlaps {b}"))
        if view.get("overflow"):
            issues.append(LayoutIssue("no_overflow", name, f"{name}: horizontal overflow"))
    return issues
