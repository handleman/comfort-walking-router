import pytest

from swarm.preflight import check, is_free_model, model_id, provider

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
