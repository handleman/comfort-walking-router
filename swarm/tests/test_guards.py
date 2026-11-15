"""Delta guard tests (026 AC-1/AC-2): stop before a judge is paid."""

from __future__ import annotations

from pathlib import Path

from swarm import guards


def test_an_empty_delta_is_no_delta(tmp_path: Path):
    record = guards.delta_record("Edit `app/main.py`.", [], tmp_path)
    assert record["reason"] == "no_delta"
    assert record["changed"] == []
    assert "no in-scope change" in guards.summary(record)


def test_a_named_file_that_was_never_created_is_incomplete(tmp_path: Path):
    (tmp_path / "README.md").write_text("# x\n")  # exists, untouched
    brief = "Create `docs/architecture/adr-013-geocoding.md` and update `README.md`."
    record = guards.delta_record(brief, ["frontend/src/App.svelte"], tmp_path)
    assert record["reason"] == "delta_incomplete"
    assert record["missing"] == ["docs/architecture/adr-013-geocoding.md"]
    assert record["untouched"] == ["README.md"]
    assert "adr-013-geocoding.md" in guards.summary(record)


def test_a_named_existing_file_untouched_is_only_a_warning(tmp_path: Path):
    (tmp_path / "README.md").write_text("# x\n")
    record = guards.delta_record("Update `README.md`.", ["app/main.py"], tmp_path)
    assert record["reason"] == ""
    assert record["untouched"] == ["README.md"]
    assert "named but untouched" in guards.summary(record)


def test_a_complete_delta_passes(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("x = 1\n")
    record = guards.delta_record("Edit `app/main.py`.", ["app/main.py"], tmp_path)
    assert record["reason"] == ""
    assert record["missing"] == [] and record["untouched"] == []


def test_the_guard_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SWARM_DELTA_GUARD", "0")
    assert guards.enabled() is False
    monkeypatch.setenv("SWARM_DELTA_GUARD", "1")
    assert guards.enabled() is True


def test_the_guard_runs_before_the_self_check_and_the_verifier():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    guard = source.index("raise _DeltaStop")
    self_check = source.index("self._self_check_phase(")
    verifier = source.index("self._verify_phase(task, _verify_kick)")
    assert guard < self_check < verifier


def test_the_reason_code_is_machine_readable():
    import types

    from swarm.flow import _reason_code

    state = types.SimpleNamespace(delta_guard={"reason": "no_delta"}, verifier={})
    assert _reason_code("needs_human", {}, state) == "no_delta"
    state.delta_guard = {"reason": "delta_incomplete"}
    assert _reason_code("needs_human", {}, state) == "delta_incomplete"


# ---------------------------------------------------------------------------
# T2 (AC-3): judges fail closed
# ---------------------------------------------------------------------------


def _parse_pass(text: str) -> tuple[str, list[str]]:
    body = (text or "").strip().lower()
    if body.startswith("pass"):
        return "pass", []
    if body.startswith("blocked"):
        return "blocked", ["nope"]
    return "unknown", []


def test_a_readable_verdict_needs_no_repair():
    calls: list[str] = []

    def repair() -> str | None:  # pragma: no cover - must not run
        calls.append("repair")
        return "pass"

    result = guards.resolve_verdict(kind="qa", first_text="PASS", parse=_parse_pass, repair=repair)
    assert result["verdict"] == "pass"
    assert result["repaired"] is False
    assert result["terminal"] is False
    assert calls == []


def test_one_repair_can_rescue_an_unreadable_verdict():
    result = guards.resolve_verdict(
        kind="verifier",
        first_text="I ran the tools and think it is probably fine.",
        parse=_parse_pass,
        repair=lambda: "BLOCKED: the endpoint is not mounted",
    )
    assert result["verdict"] == "blocked"
    assert result["repaired"] is True
    assert result["terminal"] is False
    assert result["findings"] == ["nope"]


def test_unknown_after_one_repair_is_terminal_not_a_pass():
    repairs: list[int] = []

    def repair() -> str | None:
        repairs.append(1)
        return "still thinking about it"

    result = guards.resolve_verdict(
        kind="qa", first_text="", parse=_parse_pass, repair=repair
    )
    assert result["verdict"] == "unknown"
    assert result["terminal"] is True
    assert result["repaired"] is True
    assert len(repairs) == 1, "the repair is bounded: exactly one call"


def test_a_failed_repair_is_terminal_and_recorded():
    def boom() -> str | None:
        raise RuntimeError("provider 500")

    result = guards.resolve_verdict(
        kind="senior", first_text="hmm", parse=_parse_pass, repair=boom
    )
    assert result["terminal"] is True
    assert "provider 500" in result["repair_error"]


def test_the_fail_closed_rule_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SWARM_JUDGE_FAIL_CLOSED", "0")
    assert guards.judge_fail_closed() is False
    result = guards.resolve_verdict(
        kind="qa", first_text="", parse=_parse_pass, repair=None
    )
    assert result["terminal"] is False
    monkeypatch.setenv("SWARM_JUDGE_FAIL_CLOSED", "1")
    assert guards.judge_fail_closed() is True


# ---------------------------------------------------------------------------
# T3 (AC-4): a correction cannot regress the build
# ---------------------------------------------------------------------------


def test_a_green_check_turned_red_is_a_regression():
    before = {"npm run check": 0, "pytest": 0}
    after = {"npm run check": 1, "pytest": 0}
    assert guards.correction_regressions(before, after) == ["npm run check"]


def test_an_already_red_check_is_not_the_corrections_fault():
    before = {"npm run check": 1}
    after = {"npm run check": 1}
    assert guards.correction_regressions(before, after) == []


def test_a_check_that_was_not_rerun_keeps_its_previous_state():
    assert guards.correction_regressions({"pytest": 0}, {}) == []


def test_the_correction_guard_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SWARM_CORRECTION_GUARD", "0")
    assert guards.correction_guard() is False
    monkeypatch.setenv("SWARM_CORRECTION_GUARD", "1")
    assert guards.correction_guard() is True


def test_a_correction_regression_is_a_typed_reason_code():
    import types

    from swarm.flow import _reason_code

    state = types.SimpleNamespace(
        correction_reverted={"step": 2, "regressed": ["npm run check"], "paths": ["App.svelte"]},
        verifier={},
    )
    assert _reason_code("needs_human", {}, state) == "correction_reverted"


# ---------------------------------------------------------------------------
# T4 (AC-5): the quota breaker
# ---------------------------------------------------------------------------


def test_quota_hits_are_counted_per_provider():
    hits: dict[str, int] = {}
    limit = 3
    assert guards.note_quota(hits, "openrouter", limit) is False
    assert guards.note_quota(hits, "zen", limit) is False
    assert guards.note_quota(hits, "openrouter", limit) is False
    assert guards.note_quota(hits, "openrouter", limit) is True
    assert hits == {"openrouter": 3, "zen": 1}


def test_the_quota_limit_defaults_to_three_and_is_configurable(monkeypatch):
    assert guards.quota_limit({}) == 3
    assert guards.quota_limit({"SWARM_QUOTA_LIMIT": "5"}) == 5
    assert guards.quota_limit({"SWARM_QUOTA_LIMIT": "nonsense"}) == 3
    assert guards.quota_limit({"SWARM_QUOTA_LIMIT": "0"}) == 1
    monkeypatch.setenv("SWARM_QUOTA_LIMIT", "2")
    assert guards.quota_limit() == 2


def test_the_quota_breaker_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SWARM_QUOTA_BREAKER", "0")
    assert guards.quota_breaker() is False
    monkeypatch.setenv("SWARM_QUOTA_BREAKER", "1")
    assert guards.quota_breaker() is True


def test_the_quota_provider_is_the_role_model_provider(monkeypatch):
    """The breaker counts the provider the *role* would call, not one global."""
    from swarm import llms
    from swarm.flow import _role_provider

    monkeypatch.setenv("SWARM_CODER_MODEL", "zen/glm-5.3-flash")
    monkeypatch.setenv("SWARM_REVIEWER_MODEL", "openrouter/nvidia/qa:free")
    monkeypatch.setenv("SWARM_SENIOR_MODEL", "openrouter/nvidia/senior:free")
    monkeypatch.setenv("SWARM_VERIFIER_MODEL", "openrouter/nvidia/verify:free")
    llms.reset_fallbacks()
    assert _role_provider("coder") == "zen"
    assert _role_provider("qa") == "openrouter"
    assert _role_provider("senior") == "openrouter"
    assert _role_provider("verifier") == "openrouter"
