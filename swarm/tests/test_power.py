"""053 follow-up: the host stays awake for the life of a flow (2026-11-26)."""

from __future__ import annotations


class _FakeProc:
    def __init__(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        self.terminated = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True


def _fake_popen(monkeypatch, store):
    def popen(argv, **kwargs):
        proc = _FakeProc(argv, **kwargs)
        store.append(proc)
        return proc

    monkeypatch.setattr("swarm.power.subprocess.Popen", popen)


def test_keep_awake_spawns_caffeinate_once(monkeypatch):
    from swarm import power

    power.release()
    monkeypatch.setattr(power, "_proc", None)
    monkeypatch.setattr(power.sys, "platform", "darwin")
    monkeypatch.setattr(power.shutil, "which", lambda name: "/usr/bin/caffeinate")
    monkeypatch.delenv("SWARM_KEEP_AWAKE", raising=False)
    procs: list[_FakeProc] = []
    _fake_popen(monkeypatch, procs)

    first = power.keep_awake()
    second = power.keep_awake()
    assert first is second
    assert len(procs) == 1
    assert procs[0].argv[0] == "/usr/bin/caffeinate"
    assert "-w" in procs[0].argv
    assert procs[0].argv[-1] == str(power.os.getpid())
    power.release()
    assert procs[0].terminated


def test_keep_awake_is_off_with_the_switch(monkeypatch):
    from swarm import power

    monkeypatch.setattr(power, "_proc", None)
    monkeypatch.setattr(power.sys, "platform", "darwin")
    monkeypatch.setattr(power.shutil, "which", lambda name: "/usr/bin/caffeinate")
    monkeypatch.setenv("SWARM_KEEP_AWAKE", "0")
    procs: list[_FakeProc] = []
    _fake_popen(monkeypatch, procs)
    assert power.keep_awake() is None
    assert procs == []


def test_keep_awake_is_a_noop_off_macos(monkeypatch):
    from swarm import power

    monkeypatch.setattr(power, "_proc", None)
    monkeypatch.setattr(power.sys, "platform", "linux")
    procs: list[_FakeProc] = []
    _fake_popen(monkeypatch, procs)
    assert power.keep_awake() is None
    assert procs == []


def test_keep_awake_survives_a_missing_binary(monkeypatch):
    from swarm import power

    monkeypatch.setattr(power, "_proc", None)
    monkeypatch.setattr(power.sys, "platform", "darwin")
    monkeypatch.setattr(power.shutil, "which", lambda name: None)
    assert power.keep_awake() is None


def test_release_is_idempotent(monkeypatch):
    from swarm import power

    monkeypatch.setattr(power, "_proc", None)
    power.release()
    power.release()
    assert power._proc is None
