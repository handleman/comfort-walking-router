"""052 layout contract tests: parse + deterministic checks (no browser)."""

from __future__ import annotations

from pathlib import Path

from swarm import layout

TOML = """
[region.top-card]
selector = "[data-testid='top-card']"
anchor = "top"
[region.map]
selector = "[data-testid='map']"
[region.sidebar]
selector = "[data-testid='sidebar']"
[region.drawer]
selector = "[data-testid='drawer']"

[control.origin-input]
selector = "[data-testid='origin-input']"
regions = ["top-card"]
[control.start-walk]
selector = "[data-testid='start-walk']"
regions = ["sidebar", "drawer"]
unique = true

[expect.desktop]
visible_regions = ["top-card", "map", "sidebar"]
hidden_regions = ["drawer"]
above = [["top-card", "map"]]
[expect.mobile]
visible_regions = ["top-card", "map", "drawer"]
hidden_regions = ["sidebar"]

[tolerance]
px = 2
overlap = 0
"""


def _contract(tmp_path: Path) -> layout.LayoutContract:
    path = tmp_path / "layout.toml"
    path.write_text(TOML)
    return layout.load_layout(path)


def _rect(x=0, y=0, w=100, h=40, visible=True, count=1):
    return {"x": x, "y": y, "w": w, "h": h, "visible": visible, "count": count}


def _facts(*, desktop_overrides=None, mobile_overrides=None):
    desktop = {
        "regions": {
            "top-card": _rect(0, 0, 1280, 120),
            "map": _rect(0, 120, 1280, 680),
            "sidebar": _rect(1000, 0, 280, 800),
            "drawer": _rect(0, 700, 1280, 100, visible=False),
        },
        "controls": {
            "origin-input": _rect(10, 10, 300, 40),
            "start-walk": _rect(1050, 200, 120, 40),
        },
        "overlaps": [],
        "overflow": False,
    }
    mobile = {
        "regions": {
            "top-card": _rect(0, 0, 390, 120),
            "map": _rect(0, 120, 390, 500),
            "sidebar": _rect(0, 0, 390, 844, visible=False),
            "drawer": _rect(0, 700, 390, 144),
        },
        "controls": {
            "origin-input": _rect(10, 10, 300, 40),
            "start-walk": _rect(20, 720, 120, 40),
        },
        "overlaps": [],
        "overflow": False,
    }
    desktop.update(desktop_overrides or {})
    mobile.update(mobile_overrides or {})
    return {"desktop": desktop, "mobile": mobile}


def test_parse_regions_controls_and_expect(tmp_path):
    contract = _contract(tmp_path)
    assert set(contract.regions) == {"top-card", "map", "sidebar", "drawer"}
    assert contract.controls["start-walk"].regions == ("sidebar", "drawer")
    assert contract.controls["start-walk"].unique is True
    assert contract.expect["mobile"].hidden_regions == ("sidebar",)
    assert contract.tolerance.px == 2.0


def test_a_healthy_layout_has_no_issues(tmp_path):
    assert layout.evaluate(_contract(tmp_path), _facts()) == []


def test_missing_control_is_reported(tmp_path):
    facts = _facts(desktop_overrides={"controls": {"origin-input": _rect(10, 10, 300, 40)}})
    issues = layout.evaluate(_contract(tmp_path), facts)
    assert any(i.check == "present" and i.target == "start-walk" for i in issues)


def test_duplicate_control_is_reported(tmp_path):
    facts = _facts(desktop_overrides={"controls": {"origin-input": _rect(), "start-walk": _rect(1050, 200, 120, 40, count=2)}})
    issues = layout.evaluate(_contract(tmp_path), facts)
    assert any(i.check == "unique" and i.target == "start-walk" for i in issues)


def test_control_outside_its_region_is_reported(tmp_path):
    # start-walk at the far left, outside both sidebar and drawer on mobile.
    facts = _facts(desktop_overrides={"controls": {"origin-input": _rect(), "start-walk": _rect(0, 0, 50, 20)}})
    issues = layout.evaluate(_contract(tmp_path), facts)
    assert any(i.check == "in_region" and i.target == "start-walk" for i in issues)


def test_region_visible_and_hidden_are_enforced(tmp_path):
    facts = _facts(
        desktop_overrides={"regions": {
            "top-card": _rect(0, 0, 1280, 120),
            "map": _rect(0, 120, 1280, 680),
            "sidebar": _rect(1000, 0, 280, 800, visible=False),
            "drawer": _rect(0, 700, 1280, 100, visible=True),
        }}
    )
    issues = layout.evaluate(_contract(tmp_path), facts)
    assert any(i.check == "region_visible" and i.target == "sidebar" for i in issues)
    assert any(i.check == "region_hidden" and i.target == "drawer" for i in issues)


def test_overlap_and_overflow_are_reported(tmp_path):
    facts = _facts(desktop_overrides={"overlaps": ["origin-input~start-walk"], "overflow": True})
    issues = layout.evaluate(_contract(tmp_path), facts)
    assert any(i.check == "no_overlap" for i in issues)
    assert any(i.check == "no_overflow" for i in issues)


def test_missing_viewport_facts_is_reported(tmp_path):
    facts = _facts()
    facts.pop("mobile")
    issues = layout.evaluate(_contract(tmp_path), facts)
    assert any(i.check == "viewport" and i.target == "mobile" for i in issues)


def test_region_order_is_enforced(tmp_path):
    # Map drawn above the top card: the order assertion must fire.
    facts = _facts(desktop_overrides={"regions": {
        "top-card": _rect(0, 200, 1280, 120),
        "map": _rect(0, 0, 1280, 200),
        "sidebar": _rect(1000, 0, 280, 800),
        "drawer": _rect(0, 700, 1280, 100, visible=False),
    }})
    issues = layout.evaluate(_contract(tmp_path), facts)
    assert any(i.check == "region_order" for i in issues)


def test_a_figma_shaped_contract_parses(tmp_path):
    """The IR is source-agnostic: a Figma-generated file drives the same checks."""
    figma = """
[region."Top / Card"]
selector = "[data-testid='top-card']"
[region."Map / Canvas"]
selector = "[data-testid='map']"
[control."Origin field"]
selector = "[data-testid='origin-input']"
regions = ["Top / Card"]
ac = "AC-2"
[expect.desktop]
visible_regions = ["Top / Card", "Map / Canvas"]
"""
    path = tmp_path / "figma.toml"
    path.write_text(figma)
    contract = layout.load_layout(path)
    assert "Top / Card" in contract.regions
    assert contract.controls["Origin field"].ac == "AC-2"
