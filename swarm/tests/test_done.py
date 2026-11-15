import json
import subprocess

from swarm.done import (
    DoneEntry,
    cache_only,
    done_entries,
    is_done,
    open_reason,
    record_done,
    spec_plan_hash,
    task_hash,
)
from swarm.spec_loader import SpecTask


def _task(task_id="T3", brief="Do the thing", acs=("AC-2",)):
    return SpecTask(id=task_id, ac_refs=tuple(acs), brief=brief)


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


def _init(repo):
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "swarm@test.local")
    _git(repo, "config", "user.name", "swarm test")


def _commit_with_trailer(repo, spec, task, taske, spech, run="run-1"):
    (repo / "x.txt").write_text(str(len(list(repo.glob("x*")))) + "x")
    _git(repo, "add", "-A")
    msg = (
        f"swarm: {spec}-{task} green\n\n"
        f"Swarm-Task: {spec}/{task}\n"
        f"Swarm-Task-Hash: {taske}\n"
        f"Swarm-Spec-Hash: {spech}\n"
        f"Swarm-Run: {run}\n"
    )
    _git(repo, "commit", "-q", "-m", msg)


def test_task_hash_tracks_brief_and_acs():
    base = task_hash(_task())
    assert base == task_hash(_task())
    assert base != task_hash(_task(brief="Do another thing"))
    assert base != task_hash(_task(acs=("AC-3",)))
    assert base == task_hash(_task(brief="  Do   the thing "))  # whitespace-normalized


def test_spec_hash_ignores_tasks_md(tmp_path):
    (tmp_path / "spec.md").write_text("spec")
    (tmp_path / "plan.md").write_text("plan")
    (tmp_path / "tasks.md").write_text("- [ ] T1: x\n")
    h1 = spec_plan_hash(tmp_path)
    (tmp_path / "tasks.md").write_text("- [x] T1: x\n")
    assert spec_plan_hash(tmp_path) == h1

    (tmp_path / "spec.md").write_text("spec v2")
    assert spec_plan_hash(tmp_path) != h1


def test_done_entries_reads_git_trailers(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init(repo)
    task = _task()
    _commit_with_trailer(repo, "001-example-app", "T3", task_hash(task), "a" * 64)
    entries = done_entries(repo)
    entry = entries["001-example-app/T3"]
    assert entry.source == "git"
    assert entry.task_hash == task_hash(task)
    assert entry.spec_hash == "a" * 64


def test_done_entries_cache_fallback(tmp_path):
    repo = tmp_path / "repo"
    (repo / "swarm" / "runs").mkdir(parents=True)
    record_done(
        repo,
        "001-example-app",
        "T3",
        task_hash_value="b" * 64,
        spec_hash_value="c" * 64,
        run_id="run-9",
    )
    entries = done_entries(repo)  # not a git repo -> cache only
    entry = entries["001-example-app/T3"]
    assert entry.source == "cache"
    assert entry.task_hash == "b" * 64
    assert entry.run == "run-9"


def test_record_done_merges_existing_cache(tmp_path):
    repo = tmp_path / "repo"
    (repo / "swarm" / "runs").mkdir(parents=True)
    record_done(repo, "001", "T1", task_hash_value="1" * 8, spec_hash_value="a" * 8, run_id="r1")
    record_done(repo, "001", "T2", task_hash_value="2" * 8, spec_hash_value="a" * 8, run_id="r2")
    cache = json.loads((repo / "swarm" / "runs" / "done.json").read_text())
    assert set(cache) == {"001/T1", "001/T2"}


def test_is_done_requires_matching_hashes():
    task = _task()
    entry = DoneEntry(task_hash=task_hash(task), spec_hash="a" * 64)
    entries = {"001-example-app/T3": entry}
    assert is_done(entries, "001-example-app", task, "a" * 64)
    assert not is_done(entries, "001-example-app", task, "b" * 64)  # spec/plan changed
    assert not is_done(entries, "001-example-app", _task(brief="changed"), "a" * 64)
    legacy = {"001-example-app/T3": DoneEntry(task_hash=task_hash(task), spec_hash="")}
    assert is_done(legacy, "001-example-app", task, "b" * 64)  # old entries stay valid


def _spec_repo(tmp_path):
    repo = tmp_path / "repo"
    spec = repo / "specs" / "001-x"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text("spec")
    (spec / "plan.md").write_text("plan")
    (spec / "tasks.md").write_text("- [ ] T1 (AC-1): first\n- [ ] T2 (AC-1): second\n")
    _init(repo)
    return repo, spec


def test_open_task_ids_skips_done_and_reopens_on_content_change(tmp_path):
    from swarm.flow import _open_task_ids
    from swarm.spec_loader import load_spec_tasks

    repo, spec = _spec_repo(tmp_path)
    path, tasks = load_spec_tasks(repo, "001-x", None)
    _commit_with_trailer(repo, "001-x", "T1", task_hash(tasks[0]), spec_plan_hash(spec))
    assert _open_task_ids(repo, path, tasks) == ["T2"]

    (spec / "plan.md").write_text("plan v2")
    assert _open_task_ids(repo, path, tasks) == ["T1", "T2"]

    (spec / "plan.md").write_text("plan")
    (spec / "tasks.md").write_text("- [ ] T1 (AC-1): changed brief\n- [ ] T2 (AC-1): second\n")
    path2, tasks2 = load_spec_tasks(repo, "001-x", None)
    assert _open_task_ids(repo, path2, tasks2) == ["T1", "T2"]


def test_resume_point_advances_past_done_task(tmp_path):
    from swarm.flow import _resume_point
    from swarm.spec_loader import load_spec_tasks

    repo, spec = _spec_repo(tmp_path)
    _, tasks = load_spec_tasks(repo, "001-x", None)
    _commit_with_trailer(repo, "001-x", "T1", task_hash(tasks[0]), spec_plan_hash(spec))
    run = repo / "swarm" / "runs" / "20260101-000000-1-aaaa"
    run.mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"spec": "001-x", "task": "T1", "status": "green"}))
    (run.parent / "latest").write_text(run.name)
    assert _resume_point(repo) == ("001-x", "T2")


def test_next_todo_skips_done_and_wraps_specs(tmp_path):
    from swarm.flow import _next_todo

    assert _next_todo(["T1", "T2", "T3"], ["T2", "T3"], "T1") == "T2"
    assert _next_todo(["T1", "T2", "T3"], ["T2"], "T3") is None
    assert _next_todo(["T1"], [], "T1") is None


def test_done_entries_normalises_a_legacy_spec_prefix(tmp_path):
    """A `007/T5` trailer must mark `007-live-position/T5` done."""
    repo = tmp_path / "repo"
    (repo / "specs" / "007-live-position").mkdir(parents=True)
    _init(repo)
    task = _task("T5")
    _commit_with_trailer(repo, "007", "T5", task_hash(task), "b" * 64)

    entries = done_entries(repo)

    assert "007/T5" not in entries
    assert is_done(entries, "007-live-position", task, "b" * 64)


# ---------------------------------------------------------------------------
# T9 (AC-10): the queue explains itself
# ---------------------------------------------------------------------------


def test_an_unrecorded_task_is_open_for_no_ledger_entry():
    task = _task()
    assert open_reason({}, "001-example-app", task, "a" * 64) == "no ledger entry"


def test_an_edited_brief_says_task_hash_changed():
    task = _task()
    entries = {"001-example-app/T3": DoneEntry(task_hash="d" * 64, spec_hash="a" * 64)}
    assert open_reason(entries, "001-example-app", task, "a" * 64) == "task hash changed"


def test_an_edited_spec_says_spec_hash_changed():
    task = _task()
    entries = {"001-example-app/T3": DoneEntry(task_hash=task_hash(task), spec_hash="a" * 64)}
    assert open_reason(entries, "001-example-app", task, "b" * 64) == "spec hash changed"


def test_a_cache_only_entry_is_reported_as_a_missing_trailer(tmp_path):
    repo = tmp_path / "repo"
    (repo / "swarm" / "runs").mkdir(parents=True)
    task = _task()
    record_done(
        repo,
        "001-example-app",
        "T3",
        task_hash_value=task_hash(task),
        spec_hash_value="a" * 64,
        run_id="run-1",
    )
    entries = done_entries(repo)
    assert cache_only(entries["001-example-app/T3"])
    assert open_reason(entries, "001-example-app", task, "a" * 64) == "missing trailer"


def test_the_queue_logs_the_reason_it_ran_a_task(tmp_path, capsys):
    from swarm.flow import _log_queue_reasons, _open_task_ids, queue_reasons
    from swarm.spec_loader import load_spec_tasks

    repo, spec = _spec_repo(tmp_path)
    path, tasks = load_spec_tasks(repo, "001-x", None)
    assert _open_task_ids(repo, path, tasks) == ["T1", "T2"]
    capsys.readouterr()  # drop anything from earlier module-level calls
    _log_queue_reasons("001-x")
    out = capsys.readouterr().out
    assert "open task 001-x/T1: no ledger entry" in out
    assert queue_reasons("001-x") == {"T1": "no ledger entry", "T2": "no ledger entry"}

    _commit_with_trailer(repo, "001-x", "T1", task_hash(tasks[0]), spec_plan_hash(spec))
    assert _open_task_ids(repo, path, tasks) == ["T2"]
    capsys.readouterr()
    _log_queue_reasons("001-x")
    out = capsys.readouterr().out
    assert "001-x/T1" not in out, "a done task is not noise in the queue log"
    assert "open task 001-x/T2" in out


def test_the_commit_trailer_uses_the_spec_directory_not_the_prefix(tmp_path, monkeypatch):
    """028-T4 was recorded as `028/T4`, so the ledger thought it was open.

    The queue keys entries by `<directory name>/<task>` (`spec_dir_name`); a
    commit made from `run.sh 028 T4` must normalise before writing the trailer.
    """
    from swarm import flow

    repo = tmp_path / "repo"
    (repo / "specs" / "028-x").mkdir(parents=True)
    (repo / "a.txt").write_text("x\n")
    monkeypatch.setattr(flow, "REPO_ROOT", repo)

    calls: list[list[str]] = []

    def fake_git(args, timeout=120):
        calls.append(list(args))
        return 0, "ok"

    monkeypatch.setattr(flow, "_git", fake_git)
    flow._commit_changes(
        "028",
        "T4",
        "do the thing",
        ["a.txt"],
        ("a.txt",),
        task_hash_value="a" * 64,
        run_id="r1",
    )
    message = next(args[args.index("-m") + 1] for args in calls if "-m" in args)
    assert "Swarm-Task: 028-x/T4" in message
    assert "Swarm-Task: 028/T4" not in message


def _real_git(repo, args):
    import subprocess

    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    return p.returncode, (p.stdout + p.stderr)[-500:]
