"""Spec acceptance pass (043, harness): the final greenlight.

Tests the parsing, discovery, verdict merge, report, and queue logic. The actual
browser pass is not unit-tested (it needs Chromium); the pure functions are.
"""

from __future__ import annotations

from swarm.acceptance import (
    AcceptanceRun,
    Check,
    Criterion,
    SpecReport,
    browser_plan,
    built_product_specs,
    global_failures,
    load_checks,
    merge_ac_verdicts,
    next_task_id,
    parse_criteria,
    parse_vision_json,
    queue_fix_tasks,
    render_report,
    run,
    spec_title,
    write_report,
)

# --- parsing ---------------------------------------------------------------


def test_parse_criteria_extracts_id_title_text():
    text = """
- **AC-1 — Full-bleed map.** The map fills the viewport at every size.
- **AC-2 — Floating top card.** The origin/destination fields render as one
  card over the map top (origin = my-location dot + "My location", destination =
  red pin).
"""
    out = parse_criteria(text)
    assert len(out) == 2
    assert out[0].id == "AC-1"
    assert out[0].title == "Full-bleed map"
    assert out[0].text == "The map fills the viewport at every size."
    assert out[1].id == "AC-2"
    assert out[1].text == 'The origin/destination fields render as one card over the map top (origin = my-location dot + "My location", destination = red pin).'


def test_parse_criteria_handles_empty():
    assert parse_criteria("") == []
    assert parse_criteria("# Heading\n\nNo ACs here.") == []


def test_spec_title_reads_first_heading(tmp_path):
    (tmp_path / "spec.md").write_text("# My Spec — Subtitle\n\nContent.\n")
    assert spec_title(tmp_path) == "My Spec — Subtitle"


def test_load_checks_from_toml(tmp_path):
    spec_dir = tmp_path / "specs" / "product" / "043-test"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Test\n")
    (spec_dir / "acceptance.toml").write_text("""
[[check]]
ac = "AC-1"
kind = "exists"
selector = "#map"
viewport = "desktop"
""")
    checks = load_checks(spec_dir)
    assert len(checks) == 1
    assert checks[0].kind == "exists"
    assert checks[0].selector == "#map"
    assert checks[0].ac == "AC-1"


# --- discovery --------------------------------------------------------------


def test_built_product_specs_skips_harness_and_unbuilt(tmp_path):
    (tmp_path / "specs" / "product").mkdir(parents=True)
    built = tmp_path / "specs" / "product" / "001-built"
    built.mkdir()
    (built / "tasks.md").write_text("- [x] T1: did it\n- [ ] T2: next\n")
    (built / "spec.md").write_text("# Built\n")

    unbuilt = tmp_path / "specs" / "product" / "002-unbuilt"
    unbuilt.mkdir()
    (unbuilt / "tasks.md").write_text("- [ ] T1: not done\n")
    (unbuilt / "spec.md").write_text("# Unbuilt\n")

    (tmp_path / "specs" / "harness").mkdir(parents=True)
    harness = tmp_path / "specs" / "harness" / "042-own"
    harness.mkdir()
    (harness / "tasks.md").write_text("- [x] T1: harness\n")
    (harness / "spec.md").write_text("# Harness\n")

    out = built_product_specs(tmp_path)
    assert len(out) == 1
    assert out[0].name == "001-built"


# --- merge ------------------------------------------------------------------


def test_merge_ac_verdicts_probe_passes_and_fails():
    criteria = [Criterion("AC-1", "Exists", ""), Criterion("AC-2", "Absent", "")]
    checks = [
        Check("AC-1", "exists", selector="#x"),
        Check("AC-2", "absent", selector="#y"),
    ]
    browser_checks = [
        {"spec": "t", "ac": "AC-1", "ok": True, "detail": "found"},
        {"spec": "t", "ac": "AC-2", "ok": False, "detail": "found 1"},
    ]
    vision = {}
    out = merge_ac_verdicts(criteria, checks, browser_checks, vision)
    assert out["AC-1"]["verdict"] == "pass"
    assert out["AC-2"]["verdict"] == "fail"


def test_merge_ac_verdicts_vision_fills_gaps():
    criteria = [Criterion("AC-1", "Exists", ""), Criterion("AC-2", "Looks", "")]
    out = merge_ac_verdicts(
        criteria, [],
        [{"spec": "t", "ac": "AC-1", "ok": True, "detail": "found"}],
        {"AC-2": {"verdict": "fail", "note": "blank map"}}
    )
    assert out["AC-1"]["verdict"] == "pass"
    assert out["AC-2"]["verdict"] == "fail"
    assert out["AC-2"]["evidence"] == "blank map"


def test_merge_ac_verdicts_unverified_when_no_probe_or_vision():
    criteria = [Criterion("AC-1", "Exists", "")]
    out = merge_ac_verdicts(criteria, [], [], {})
    assert out["AC-1"]["verdict"] == "unverified"


def test_global_failures_catches_map_tile_and_dupes():
    views = {
        "desktop": {
            "leaflet": True,
            "tiles": 0,
            "duplicateButtons": ["My location"],
            "zeroSize": 2,
            "overflow": False,
            "consoleErrors": ["TypeError: foo"],
            "routeRequests": 0,
        },
        "mobile": {
            "leaflet": True,
            "tiles": 4,
            "duplicateButtons": [],
            "zeroSize": 0,
            "overflow": True,
            "consoleErrors": [],
            "routeRequests": 0,
        },
    }
    fails = global_failures(views)
    assert any("0 tiles" in f for f in fails)
    assert any("console error" in f for f in fails)
    assert any("duplicate" in f for f in fails)
    assert any("zero size" in f for f in fails)
    assert any("overflow" in f for f in fails)


# --- report + queue ---------------------------------------------------------


def test_spec_report_verdict_fail_on_global_failures():
    report = SpecReport(
        spec="t",
        title="T",
        criteria=[Criterion("AC-1", "One", "")],
        checks=[],
        global_failures=["map has 0 tiles"],
    )
    assert report.verdict == "FAIL"


def test_spec_report_verdict_pass_when_all_pass():
    report = SpecReport(
        spec="t",
        title="T",
        criteria=[Criterion("AC-1", "One", "")],
        checks=[],
    )
    report.ac_verdicts = {"AC-1": {"verdict": "pass", "evidence": "", "source": "probe"}}
    assert report.verdict == "PASS"


def test_spec_report_verdict_unverified_when_no_votes():
    report = SpecReport(
        spec="t",
        title="T",
        criteria=[Criterion("AC-1", "One", "")],
        checks=[],
    )
    assert report.verdict == "UNVERIFIED"


def test_render_report_outputs_markdown():
    report = SpecReport(
        spec="t",
        title="Test",
        criteria=[Criterion("AC-1", "Full-bleed map", "")],
        checks=[],
    )
    report.ac_verdicts = {
        "AC-1": {"verdict": "pass", "evidence": "exists", "source": "probe"},
    }
    out = render_report(report, generated="2026-11-22T00:00:00Z")
    assert "# t — Acceptance" in out
    assert "| AC-1 | PASS | probe | exists |" in out
    assert "Verdict: **PASS**" in out


def test_write_report(tmp_path):
    report = SpecReport(
        spec="t",
        title="Test",
        criteria=[],
        checks=[],
    )
    report.ac_verdicts = {"AC-1": {"verdict": "pass", "evidence": "", "source": "probe"}}
    path = write_report(tmp_path, report)
    assert path.name == "acceptance.md"
    assert path.exists()
    assert "AC-1" in path.read_text()


def test_next_task_id():
    assert next_task_id("- [ ] T1: a\n- [ ] T2: b\n- [ ] T3: c\n") == 4
    assert next_task_id("- [ ] T1: a\n") == 2
    assert next_task_id("") == 1
    assert next_task_id("- [x] T1: done\n") == 2


def test_queue_fix_tasks_appends_and_dedupes():
    text = "- [ ] T1: original\n"
    failures = [
        {"ac": "AC-2", "title": "No route trigger", "evidence": "/route missing", "file": ""},
        {"ac": "AC-2", "title": "Dup route", "evidence": "dup", "file": ""},
    ]
    new_text, added = queue_fix_tasks(text, failures, date="2026-11-22")
    assert len(added) == 1
    assert "T2" in added[0]
    assert "AC-2" in added[0]
    assert "acceptance" in added[0]
    assert "- [ ] T1: original\n" in new_text
    assert "- [ ] T2" in new_text


def test_queue_fix_tasks_respects_open_dedup():
    text = "- [ ] T5 (AC-2): acceptance pass says fix\n"
    new_text, added = queue_fix_tasks(text, [{"ac": "AC-2", "title": "x", "evidence": "y"}], date="2026-11-22")
    assert len(added) == 0
    assert new_text == text


# --- vision parse -----------------------------------------------------------


def test_parse_vision_json():
    raw = '{"AC-1": {"verdict": "pass", "note": "fine"}}'
    out = parse_vision_json(raw)
    assert out["AC-1"]["verdict"] == "pass"
    assert out["AC-1"]["note"] == "fine"


def test_parse_vision_json_ignores_garbage():
    assert parse_vision_json("not json") == {}
    assert parse_vision_json("{}") == {}


# --- browser plan -----------------------------------------------------------


def test_browser_plan_builds_check_list(tmp_path):
    specs = [tmp_path]
    plan = browser_plan(specs, base_url="http://localhost:5173/", out_dir=tmp_path / "out")
    assert plan["baseUrl"] == "http://localhost:5173/"
    assert len(plan["views"]) == 2
    assert plan["views"][0]["width"] == 1280
    assert plan["views"][1]["width"] == 390


# --- run() smoke ------------------------------------------------------------


def test_run_returns_unverified_when_no_specs(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARM_ACCEPT_VISION", "0")
    monkeypatch.setattr("swarm.acceptance.built_product_specs", lambda repo: [])
    result = run(repo=tmp_path, queue=False, build=False, base_url="http://x/")
    assert result.verdict == "UNVERIFIED"
    assert len(result.reports) == 0


def test_run_with_mock_browser_and_vision(tmp_path, monkeypatch):
    spec_dir = tmp_path / "specs" / "product" / "043-test"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("- **AC-1 — Exists.** Element #x.\n")
    (spec_dir / "tasks.md").write_text("- [x] T1: built\n- [ ] T2: next\n")
    (spec_dir / "acceptance.toml").write_text("""
[[check]]
ac = "AC-1"
kind = "exists"
selector = "#x"
""")

    monkeypatch.setattr("swarm.acceptance.built_product_specs", lambda repo: [spec_dir])
    monkeypatch.setattr(
        "swarm.acceptance.judge_vision",
        lambda report: {"AC-1": {"verdict": "pass", "note": "saw it"}},
    )

    def fake_browser(plan):
        return {
            "shots": {},
            "views": {"desktop": {"leaflet": True, "tiles": 3, "duplicateButtons": [], "zeroSize": 0, "overflow": False, "consoleErrors": [], "routeRequests": 0}},
            "checks": [{"spec": "043-test", "ac": "AC-1", "ok": True, "detail": "exists"}],
        }

    monkeypatch.setattr("swarm.acceptance.run_browser", fake_browser)
    result = run(repo=tmp_path, queue=False, build=False, base_url="http://x/", browser_runner=fake_browser)
    assert result.verdict == "PASS"
    assert len(result.reports) == 1
    assert result.reports[0].ac_verdicts["AC-1"]["verdict"] == "pass"


def test_run_vision_called_for_no_probe(tmp_path, monkeypatch):
    spec_dir = tmp_path / "specs" / "product" / "043-v"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("- **AC-1 — Looks fine.** Screenshot shows map.\n")
    (spec_dir / "tasks.md").write_text("- [x] T1: built\n")

    monkeypatch.setattr("swarm.acceptance.built_product_specs", lambda repo: [spec_dir])
    monkeypatch.setattr(
        "swarm.acceptance.judge_vision",
        lambda report: {"AC-1": {"verdict": "fail", "note": "blank map"}},
    )

    def fake_browser(plan):
        return {
            "shots": {"desktop": "/tmp/desktop.png"},
            "views": {"desktop": {"leaflet": True, "tiles": 0, "duplicateButtons": [], "zeroSize": 0, "overflow": False, "consoleErrors": [], "routeRequests": 0}},
            "checks": [],
        }

    result = run(repo=tmp_path, queue=False, build=False, base_url="http://x/", browser_runner=fake_browser)
    assert result.verdict == "FAIL"
    assert result.reports[0].ac_verdicts["AC-1"]["verdict"] == "fail"
    assert result.reports[0].ac_verdicts["AC-1"]["evidence"] == "blank map"


# --- acceptance run ---------------------------------------------------------


def test_acceptance_run_exit_code():
    assert AcceptanceRun("PASS", [], 0).exit_code == 0
    assert AcceptanceRun("FAIL", [], 0).exit_code == 1
    assert AcceptanceRun("UNVERIFIED", [], 0).exit_code == 0


# --- entrypoint -------------------------------------------------------------


def test_main_disabled(monkeypatch):
    monkeypatch.setenv("SWARM_ACCEPT", "0")
    from swarm.acceptance import main
    assert main([]) == 0


def test_main_returns_exit_code(monkeypatch):
    monkeypatch.setenv("SWARM_ACCEPT", "1")
    monkeypatch.setenv("SWARM_ACCEPT_VISION", "0")
    from swarm.acceptance import main
    # No specs built → UNVERIFIED, exit 0
    result = main(["--spec", "999-no-such-spec"])
    assert result == 0