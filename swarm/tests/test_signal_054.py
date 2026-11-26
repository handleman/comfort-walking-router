"""054 AC-1: every e2e entry point builds before it serves `dist/`."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def test_the_playwright_config_builds_before_serving():
    config = (FRONTEND / "playwright.config.ts").read_text()
    assert "globalSetup" in config
    setup = (FRONTEND / "e2e" / "global-setup.ts").read_text()
    assert "npm run build" in setup
    # The preview server is what serves dist/; it must be the global setup's job.
    assert "preview" in config


def test_the_npm_script_is_the_one_the_harness_runs():
    """`swarm.e2e` records `npm --prefix frontend run test:e2e` as the evidence."""
    package = (FRONTEND / "package.json").read_text()
    assert '"test:e2e"' in package
    from swarm import e2e

    assert ["npm", "--prefix", "frontend", "run", "test:e2e"] == e2e.agent_commands("")[1]
