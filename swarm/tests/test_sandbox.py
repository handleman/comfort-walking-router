import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _dry(extra_args: list[str] | None = None, env: dict[str, str] | None = None):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("SWARM_SANDBOX_")}
    clean.update(env or {})
    return subprocess.run(
        ["bash", str(REPO / "swarm" / "sandbox.sh"), "--dry-run", *(extra_args or [])],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=clean,
        check=True,
    )


def test_sandbox_mounts_only_the_repo_and_drops_caps():
    out = _dry().stdout
    assert "docker run" in out
    assert f"-v {REPO}:/work" in out
    assert "--cap-drop=ALL" in out
    assert "--security-opt=no-new-privileges" in out
    assert "host.docker.internal" in out
    assert ".ssh" not in out  # SSH is not mounted by default


def test_sandbox_defaults_to_no_commit():
    out = _dry(["001", "T3"]).stdout
    assert "--no-commit" in out


def test_sandbox_with_no_args_resumes():
    out = _dry().stdout
    assert "--resume" in out and "--no-commit" in out


def test_sandbox_can_opt_into_commits():
    out = _dry(env={"SWARM_SANDBOX_ALLOW_COMMIT": "1"}).stdout
    assert "--no-commit" not in out


def test_sandbox_ssh_mount_is_opt_in():
    out = _dry(env={"SWARM_SANDBOX_SSH": "1"}).stdout
    assert ".ssh:/tmp/.ssh:ro" in out


def test_sandbox_masks_dotenv_when_present():
    if not (REPO / ".env").is_file():
        pytest.skip("no .env in this checkout")
    assert "/dev/null:/work/.env:ro" in _dry().stdout


def test_dockerfile_and_build_context_are_sane():
    dockerfile = (REPO / "swarm" / "docker" / "Dockerfile").read_text()
    assert 'ENTRYPOINT ["python", "-m", "swarm.flow"]' in dockerfile
    assert "requirements.txt" in dockerfile and "requirements-dev.txt" in dockerfile
    assert "PYTHONPATH=/work" in dockerfile

    ignore = (REPO / ".dockerignore").read_text().splitlines()
    for pattern in (".env", "swarm/.venv", "swarm/runs", "frontend/node_modules"):
        assert pattern in ignore


def test_sandbox_script_requires_docker_only_outside_dry_run():
    script = (REPO / "swarm" / "sandbox.sh").read_text()
    assert "docker daemon is not running" in script
    assert "SWARM_SANDBOX_NO_BUILD" in script
