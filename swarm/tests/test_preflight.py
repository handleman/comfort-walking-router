from pathlib import Path

import pytest

from swarm import preflight
from swarm.preflight import check, is_free_model, model_id, provider


@pytest.fixture(autouse=True)
def _fake_repo(tmp_path, monkeypatch):
    """Clean checkouts have no project venvs; point the venv checks at a temp repo."""
    for rel in (".venv/bin/python", "swarm/.venv/bin/python"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)


LOCAL_ENV = {
    "SWARM_PLANNER_MODEL": "ollama/swarm-coder:latest",
    "SWARM_CODER_MODEL": "ollama/swarm-coder:latest",
    "SWARM_REVIEWER_MODEL": "ollama/swarm-qa:latest",
    "SWARM_SENIOR_MODEL": "ollama/swarm-qa:latest",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "SWARM_ALLOW_PAID": "0",
    "PATH": "/usr/bin:/bin",
}


def _tags(*names):
    def fetch(url, **_):
        assert url.endswith("/api/tags")
        return {"models": [{"name": n} for n in names]}

    return fetch


def _which(_binary, path=None):
    return f"/fake/{_binary}"


def _ok_env(**over):
    env = dict(LOCAL_ENV)
    env.update(over)
    return env


def test_local_config_passes():
    env = _ok_env()
    assert check(env, fetch=_tags("swarm-coder:latest", "swarm-qa:latest"), which=_which) == []


def test_missing_model_var_is_reported():
    env = _ok_env(SWARM_SENIOR_MODEL="")
    problems = check(env, fetch=_tags("swarm-coder:latest", "swarm-qa:latest"), which=_which)
    assert any(p.check == "SWARM_SENIOR_MODEL" for p in problems)


def test_whitespace_model_id_is_reported():
    env = _ok_env(SWARM_CODER_MODEL="ollama/swarm-coder:latest ")
    problems = check(env, fetch=_tags("swarm-coder:latest", "swarm-qa:latest"), which=_which)
    assert any("whitespace" in p.detail for p in problems)


def test_paid_model_blocked_without_allow_paid():
    env = _ok_env(SWARM_SENIOR_MODEL="openrouter/deepseek/deepseek-v4.1-flash")
    problems = check(env, offline=True, which=_which)
    assert any("paid model" in p.detail for p in problems)

    env["SWARM_ALLOW_PAID"] = "1"
    env["OPENROUTER_API_KEY"] = "test-key"
    assert check(env, offline=True, which=_which) == []


def test_missing_ollama_model_is_reported():
    problems = check(_ok_env(), fetch=_tags("swarm-coder:latest"), which=_which)
    assert any("not pulled" in p.detail and "swarm-qa" in p.detail for p in problems)


def test_unreachable_ollama_is_reported():
    def fetch(url, **_):
        raise OSError("connection refused")

    problems = check(_ok_env(), fetch=fetch, which=_which)
    assert any(p.check == "ollama" and "not reachable" in p.detail for p in problems)


def test_openrouter_model_must_exist():
    env = _ok_env(
        SWARM_PLANNER_MODEL="openrouter/nvidia/gone-model:free",
        SWARM_SENIOR_MODEL="openrouter/nvidia/known:free",
        OPENROUTER_API_KEY="test-key",
    )

    def fetch(url, **_):
        assert "openrouter.ai" in url
        return {"data": [{"id": "nvidia/known:free"}]}

    problems = check(env, fetch=fetch, which=_which)
    assert any(p.check == "SWARM_PLANNER_MODEL" and "not offered" in p.detail for p in problems)
    assert not any(p.check == "SWARM_SENIOR_MODEL" for p in problems)


def test_zen_role_requires_key():
    env = _ok_env(SWARM_REVIEWER_MODEL="zen/some-model-free")
    problems = check(env, offline=True, which=_which)
    assert any("OPENCODE_API_KEY" in p.detail for p in problems)


def test_offline_skips_provider_requests():
    def boom(url, **_):
        raise AssertionError("network should not be called")

    env = _ok_env(SWARM_PLANNER_MODEL="openrouter/nvidia/known:free", OPENROUTER_API_KEY="k")
    assert check(env, fetch=boom, which=_which, offline=True) == []


def test_missing_gate_binary_is_reported():
    def which(binary, path=None):
        return None if binary == "mypy" else f"/fake/{binary}"

    env = _ok_env()
    problems = check(env, fetch=_tags("swarm-coder:latest", "swarm-qa:latest"), which=which)
    assert any(p.check == "gates" and "mypy" in p.detail for p in problems)


@pytest.mark.parametrize(
    ("model", "prov", "mid"),
    [
        ("ollama/qwen3.5:9b", "ollama", "qwen3.5:9b"),
        ("zen/glm-5.3-flash", "zen", "glm-5.3-flash"),
        ("openrouter/nvidia/x:free", "openrouter", "nvidia/x:free"),
    ],
)
def test_provider_and_model_id(model, prov, mid):
    assert provider(model) == prov
    assert model_id(model) == mid


def test_free_model_detection_matches_guard():
    assert is_free_model("ollama/anything")
    assert is_free_model("openrouter/x:free")
    assert is_free_model("zen/some-free")
    assert is_free_model("openai/muse-spark-1.3-contributor-free")
    assert not is_free_model("zen/glm-5.3-flash")


def test_unmerged_worktree_blocks_a_run(monkeypatch):
    """A leftover conflicted stash pop must not reach the gates or a commit."""
    monkeypatch.setattr(preflight, "unmerged_paths", lambda repo_root=None: ["frontend/src/App.svelte"])
    problems = check(
        _ok_env(),
        fetch=_tags("swarm-coder:latest", "swarm-qa:latest"),
        which=_which,
    )
    tags = [p.check for p in problems]
    assert "worktree" in tags
    assert "App.svelte" in next(p.detail for p in problems if p.check == "worktree")


# ---------------------------------------------------------------------------
# T8 (AC-9): the factories are built exactly as the run builds them
# ---------------------------------------------------------------------------


def test_a_broken_factory_is_a_preflight_problem(monkeypatch):
    """A paid planner with allow_paid=False must fail here, not in the crew."""
    from swarm.preflight import factory_problems

    def paid_only():
        raise PermissionError("paid model requires SWARM_ALLOW_PAID=1")

    monkeypatch.setattr(preflight, "factories", lambda: {"planner": paid_only})
    problems = factory_problems()
    assert len(problems) == 1
    assert problems[0].check == "factory planner"
    assert "SWARM_ALLOW_PAID" in problems[0].detail


def test_every_factory_building_is_not_a_problem(monkeypatch):
    from swarm.preflight import factory_problems

    monkeypatch.setattr(
        preflight, "factories", lambda: {"coder": lambda: object(), "qa": lambda: object()}
    )
    assert factory_problems() == []


def test_the_role_list_matches_the_crews():
    names = {name for name, _ in preflight.ROLE_FACTORIES}
    assert names == {"planner", "coder", "reviewer", "senior", "verifier"}
    assert set(preflight.factories()) == names


def test_a_walled_role_fails_the_probe(monkeypatch):
    from swarm.preflight import probe_roles

    def walled(_llm):
        raise RuntimeError("429 free-models-per-day")

    problems = probe_roles(roles={"coder": lambda: object()}, call=walled)
    assert len(problems) == 1
    assert problems[0].check == "probe coder"
    assert "free-models-per-day" in problems[0].detail


def test_a_healthy_role_passes_the_probe():
    from swarm.preflight import probe_roles

    assert probe_roles(roles={"coder": lambda: object()}, call=lambda _llm: "ok") == []


def test_the_probe_is_skipped_offline():
    from swarm.preflight import probe_roles

    def boom(_llm):  # pragma: no cover - must not run
        raise AssertionError("offline must not call a provider")

    assert probe_roles(offline=True, roles={"coder": lambda: object()}, call=boom) == []


def test_check_can_probe_the_real_factories(monkeypatch):
    """`check(probe_factories=True)` reports broken factories; default does not."""

    def boom():
        raise PermissionError("no key")

    monkeypatch.setattr(preflight, "factories", lambda: {"planner": boom})
    base = {"fetch": _tags("swarm-coder:latest", "swarm-qa:latest"), "which": _which}
    assert not any(p.check.startswith("factory") for p in check(_ok_env(), **base))
    problems = check(_ok_env(), probe_factories=True, **base)
    assert any(p.check == "factory planner" for p in problems)


def test_missing_playwright_blocks_preflight(monkeypatch, tmp_path):
    """026 AC-8: an e2e repo without the suite installed must not start."""
    (tmp_path / "frontend" / "e2e").mkdir(parents=True)
    (tmp_path / "frontend" / "playwright.config.ts").write_text("export default {}\n")
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)
    problems = check(
        _ok_env(), fetch=_tags("swarm-coder:latest", "swarm-qa:latest"), which=_which
    )
    assert any(p.check == "e2e" for p in problems)


def _fake_playwright(tmp_path, location: Path) -> Path:
    binary = tmp_path / "frontend" / "node_modules" / ".bin" / "playwright"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text(
        "#!/bin/sh\n"
        f"echo '  Install location:    {location}'\n"
        "echo '  Download url:        https://example.invalid/x.zip'\n"
    )
    binary.chmod(0o755)
    return binary


def test_missing_browser_binaries_fail_preflight(tmp_path):
    """026 AC-8: `npm install` does not download Chromium; a run would fail late."""
    _fake_playwright(tmp_path, tmp_path / "no-such-browsers" / "chromium-1")
    from swarm import e2e as e2e_suite

    problems = e2e_suite.browsers(tmp_path)
    assert len(problems) == 1
    assert "browsers are not installed" in problems[0]


def test_installed_browser_binaries_pass(tmp_path):
    installed = tmp_path / "ms-playwright" / "chromium-1"
    installed.mkdir(parents=True)
    _fake_playwright(tmp_path, installed)
    from swarm import e2e as e2e_suite

    assert e2e_suite.browsers(tmp_path) == []


def test_no_playwright_binary_is_reported_once(tmp_path):
    """The missing binary is `available`'s problem, not two problems."""
    from swarm import e2e as e2e_suite

    problems = e2e_suite.available(tmp_path)
    assert any("playwright is missing" in p for p in problems)
    assert not any("browsers are not installed" in p for p in problems)
