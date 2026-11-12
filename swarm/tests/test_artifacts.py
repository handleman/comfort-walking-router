"""Deterministic artifact-completeness tests (021 T10)."""

from __future__ import annotations

from pathlib import Path

from swarm import artifacts


def _write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def test_a_truncated_python_file_is_named(tmp_path: Path):
    _write(tmp_path, "tests/test_x.py", "def _build(start: str\n")
    problems = artifacts.incomplete(["tests/test_x.py"], tmp_path)
    assert any("does not parse" in p for p in problems)


def test_a_python_test_without_tests_is_named(tmp_path: Path):
    _write(tmp_path, "tests/test_x.py", "def helper():\n    return 1\n")
    problems = artifacts.incomplete(["tests/test_x.py"], tmp_path)
    assert problems == [
        "tests/test_x.py: no test function (the file parses but contains no test)"
    ]


def test_a_complete_python_test_passes(tmp_path: Path):
    _write(tmp_path, "tests/test_x.py", "def test_ok():\n    assert True\n")
    assert artifacts.incomplete(["tests/test_x.py"], tmp_path) == []


def test_a_test_class_counts(tmp_path: Path):
    _write(tmp_path, "tests/test_x.py", "class TestX:\n    def test_ok(self):\n        assert True\n")
    assert artifacts.incomplete(["tests/test_x.py"], tmp_path) == []


def test_a_frontend_test_without_a_case_is_named(tmp_path: Path):
    _write(tmp_path, "frontend/src/lib/x.test.ts", "export const helper = 1\n")
    problems = artifacts.incomplete(["frontend/src/lib/x.test.ts"], tmp_path)
    assert problems and "no test case" in problems[0]


def test_a_frontend_test_case_passes(tmp_path: Path):
    _write(tmp_path, "frontend/src/lib/x.test.ts", "it('works', () => { expect(1).toBe(1) })\n")
    assert artifacts.incomplete(["frontend/src/lib/x.test.ts"], tmp_path) == []


def test_non_test_python_may_contain_no_tests(tmp_path: Path):
    _write(tmp_path, "app/scoring.py", "def score():\n    return 1\n")
    assert artifacts.incomplete(["app/scoring.py"], tmp_path) == []


def test_the_self_check_adds_the_artifact_check():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "artifacts.incomplete(" in source
    assert 'codes["harness: artifacts"] = 1' in source
