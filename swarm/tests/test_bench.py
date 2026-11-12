"""Offline bench tests (020 T1): corpus shape, determinism, no model calls."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from swarm.bench import corpus, score

REPO = Path(__file__).resolve().parents[2]


def _case(**overrides) -> dict:
    base = {
        "id": "020-harness-efficiency-T1",
        "spec": "020-harness-efficiency",
        "task": "T1",
        "brief": "Add `swarm/bench/corpus.py` and a test in `swarm/tests/test_bench.py`.",
        "ac_refs": ["AC-1"],
        "ac_text": ["- **AC-1** — a frozen corpus."],
        "plan_text": ["- `swarm/bench/corpus.py` builds cases."],
        "steps": ["Edit `swarm/bench/corpus.py` — build the corpus."],
        "changed": ["swarm/bench/corpus.py"],
        "files": [{"path": "swarm/bench/corpus.py", "content": "x = 1\n", "sha256": "0" * 64, "chars": 6}],
        "gates": {"pytest -q": 0, "scope": 0},
        "transcript": "$ pytest -q\nexit=0\n(clean)",
        "recorded": {"status": "green", "fix_rounds": 1},
    }
    base.update(overrides)
    base["report_fixture"] = corpus.failing_transcript(base)
    return base


# ---- corpus selection helpers ----


def test_brief_paths_reads_backticks_and_bare_paths_once():
    brief = (
        "Add `GET /geocode` in `app/main.py` plus a test in tests/test_geocode.py, "
        "and mount `app/main.py` only once."
    )
    assert corpus.brief_paths(brief) == ["app/main.py", "tests/test_geocode.py"]


def test_brief_paths_ignores_directories_and_command_text():
    assert corpus.brief_paths("Run `pytest -q` and edit app/scoring.py") == ["app/scoring.py"]
    assert corpus.brief_paths("no paths here") == []


def test_case_ids_are_path_safe():
    assert corpus.case_id("007-live-position", "T2") == "007-live-position-T2"


def test_step_fixture_is_one_file_per_step_and_capped():
    changed = [f"frontend/src/lib/f{i}.ts" for i in range(12)]
    steps = corpus.step_fixture(changed, "T3", ["AC-3"])
    assert len(steps) == corpus.MAX_STEPS
    assert changed[0] in steps[0]


def test_failing_gate_choice_is_independent_of_dict_order():
    gates = {"pytest -q": 0, "ruff check .": 0, "scope": 0}
    assert corpus.failing_gate({"gates": dict(reversed(list(gates.items())))}) == "ruff check ."


def test_failing_transcript_is_bounded_and_marks_one_gate_red():
    case = _case()
    text = case["report_fixture"]
    assert "$ pytest -q" in text and "exit=1" in text
    assert len(text) <= corpus.MAX_TRANSCRIPT_CHARS


# ---- scoring: prompts and reports ----


def test_score_case_counts_the_loop_it_measured():
    case = _case()
    row = score.score_case(case)
    assert row["steps"] == 1
    assert row["fix_rounds"] == 1
    assert row["step_prompt_chars"] > 0 and row["qa_prompt_chars"] > 0
    assert row["fix_prompt_chars"] > 0 and row["verify_prompt_chars"] > 0
    expected = (
        row["step_prompt_chars"]
        + 2 * row["qa_prompt_chars"]  # fix_rounds + 1 QA rounds
        + row["fix_prompt_chars"]
        + row["verify_prompt_chars"]
    )
    assert row["task_prompt_chars"] == expected
    assert row["est_tokens"] == expected // 4


def test_report_fixture_carries_the_failing_tail_not_only_key_lines(tmp_path):
    from swarm import compaction
    from swarm.evidence import report_text

    case = _case()
    report = score.report_fixture(case)
    unspilled, _ = compaction.spill_report(report, tmp_path, enabled_flag=False)
    text = report_text(unspilled)
    assert len(text) >= 3000, "the fixture must exercise the real failure-tail budget"
    assert "FAILING GATES" in text
    assert "corpus.py:12" in text

    spilled, record = compaction.spill_report(
        score.report_fixture(case), tmp_path, enabled_flag=True
    )
    compact = report_text(spilled)
    assert record["gate_logs"], "a long tail is spilled (020 T4)"
    assert "corpus.py:12" in compact  # the key line survives
    assert "full log: gate_logs/" in compact  # and the full text has a locator
    assert len(compact) < len(text)


def test_report_is_renderable_without_a_model_and_identical_twice():
    case = _case()
    assert score.report_fixture_text(case) == score.report_fixture_text(case)


def test_bench_env_is_restored(monkeypatch):
    monkeypatch.setenv("SWARM_CODER_MODEL", "custom/model")
    before = os.environ["SWARM_CODER_MODEL"]
    with score.bench_env():
        assert os.environ["SWARM_CODER_MODEL"] == "ollama/bench"
    assert os.environ["SWARM_CODER_MODEL"] == before


def test_compare_reports_deltas_and_tolerates_a_new_case():
    baseline = {"cases": {"a": {"task_prompt_chars": 1000, "report_chars": 400, "gates_per_round": 6}}}
    current = {
        "cases": {
            "a": {"task_prompt_chars": 700, "report_chars": 200, "gates_per_round": 3},
            "b": {"task_prompt_chars": 10, "report_chars": 10, "gates_per_round": 1},
        }
    }
    rows = {row["id"]: row for row in score.compare(baseline, current)}
    assert rows["a"]["task_delta_pct"] == -30.0
    assert rows["a"]["report_delta_pct"] == -50.0
    assert rows["a"]["gates_delta"] == -3
    assert rows["b"]["before"] is None


# ---- the committed corpus and its baseline ----


@pytest.mark.skipif(not (REPO / "swarm" / "bench" / "corpus").is_dir(), reason="corpus not built")
def test_committed_corpus_is_loadable_and_matches_its_baseline():
    cases = corpus.load_corpus(REPO)
    assert len(cases) >= 10
    baseline = score.load_baseline(REPO / "swarm" / "bench" / "baseline.json")
    assert baseline, "baseline.json must be committed before prompt/gate changes (AC-1)"
    assert baseline["corpus_digest"] == corpus.corpus_digest(cases)


@pytest.mark.skipif(not (REPO / "swarm" / "bench" / "corpus").is_dir(), reason="corpus not built")
def test_every_committed_case_pins_a_commit_and_a_content_hash():
    for case in corpus.load_corpus(REPO):
        assert case["green_sha"] and case["base_sha"] == case["green_sha"] + "^"
        assert case["steps"] and len(case["steps"]) <= corpus.MAX_STEPS
        for entry in case["files"]:
            assert len(entry["sha256"]) == 64
            assert entry["content"] or entry.get("omitted")


def test_cli_rejects_an_unknown_case(capsys):
    from swarm.bench.__main__ import main

    assert main(["--case", "no-such-case"]) == 1
    assert "unknown case" in capsys.readouterr().err


def test_cli_json_prints_a_score(tmp_path: Path, capsys):
    from swarm.bench.__main__ import main

    cases = corpus.load_corpus(REPO) if (REPO / "swarm" / "bench" / "corpus").is_dir() else []
    if not cases:
        pytest.skip("corpus not built")
    assert main(["--json", "--case", cases[0]["id"]]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["totals"]["cases"] == 1


# ---- 020 AC-2: the bench records the stable prefix ----


def test_bench_records_a_stable_prefix_hash():
    case = _case()
    row = score.score_case(case)
    assert len(row["prefix_sha256"]) == 16
    assert row["prefix_chars"] > 200
    assert row["prefix_sha256"] == score.score_case(case)["prefix_sha256"]


def test_prefix_hash_changes_when_the_brief_changes():
    a = score.score_case(_case())
    b = score.score_case(_case(brief="Add `swarm/bench/other.py` instead."))
    assert a["prefix_sha256"] != b["prefix_sha256"]


def test_recorded_prefix_is_the_head_of_the_real_step_prompt():
    case = _case()
    from swarm.crew import build_step_crew
    from swarm.prompts import prompt_prefix
    from swarm.spec_loader import SpecTask

    task = SpecTask(id=case["task"], ac_refs=tuple(case["ac_refs"]), brief=case["brief"])
    with score.bench_env():
        crew = build_step_crew(case["spec"], task, case["steps"][0], 1, 1)
    prefix_text, prefix_hash = prompt_prefix(task, case["spec"], "step")
    assert score.score_case(case)["prefix_sha256"] == prefix_hash
    assert score.crew_prompt(crew).startswith(prefix_text)
