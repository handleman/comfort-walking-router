"""042 Swarm Visual QA — Playwright runner for deterministic DOM checks and screenshots.

Opens the built app via the existing frontend/playwright.config.ts setup,
screenshots desktop + mobile, and returns DOM facts for the visual-qa agent.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class VisualFact:
    """Deterministic DOM fact collected by Playwright."""

    map_tile_count: int = 0
    start_form_count: int = 0
    end_form_count: int = 0
    leftover_step_labels: list[str] = None  # PLAN/REVIEW/WALK etc.
    top_card_button_count: int = 0
    console_errors: list[str] = None
    screenshot_desktop_b64: str = ""
    screenshot_mobile_b64: str = ""

    def __post_init__(self):
        if self.leftover_step_labels is None:
            self.leftover_step_labels = []
        if self.console_errors is None:
            self.console_errors = []

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def has_obvious_breakage(self) -> bool:
        """Quick deterministic red flags — no model needed."""
        if self.map_tile_count == 0:
            return True
        if self.start_form_count != 1 or self.end_form_count != 1:
            return True
        return self.top_card_button_count == 0


# Constants for the fixture-backed frontend
DEFAULT_BASE_URL = "http://localhost:5173"
DEFAULT_API_URL = "http://localhost:8000"
DESKTOP_VIEWPORT = {"width": 1280, "height": 800}
MOBILE_VIEWPORT = {"width": 390, "height": 844}


async def _run_playwright_visual_check(
    base_url: str,
    *,
    headed: bool = False,
    slow_mo: int = 0,
) -> VisualFact:
    """Run Playwright to collect screenshots and DOM facts."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("playwright not installed — run `make e2e` setup first")

    fact = VisualFact()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed, slow_mo=slow_mo)
        context = await browser.new_context()
        page = await context.new_page()

        # Collect console errors
        page.on("console", lambda msg: fact.console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: fact.console_errors.append(str(err)))

        # Navigate and wait for network idle
        await page.goto(base_url, wait_until="networkidle", timeout=30_000)

        # ---- Deterministic DOM checks (desktop) ----
        # Map tiles: Leaflet creates <img class="leaflet-tile"> elements
        fact.map_tile_count = await page.locator(".leaflet-tile").count()

        # Start/End forms: count the search input fields
        fact.start_form_count = await page.locator('input[placeholder*="Start" i], input[placeholder*="origin" i]').count()
        fact.end_form_count = await page.locator('input[placeholder*="End" i], input[placeholder*="destination" i]').count()

        # Top-card buttons: look for route action buttons
        fact.top_card_button_count = await page.locator("button:has-text('Route'), button:has-text('Find'), button:has-text('Go'), button[aria-label*='route' i]").count()

        # Leftover step labels (from planner/coder output leaked into UI)
        step_labels = await page.locator("text=/^(PLAN|REVIEW|WALK|STEP)\\b/i").all_text_contents()
        fact.leftover_step_labels = [s.strip() for s in step_labels if s.strip()]

        # Screenshot desktop
        await page.set_viewport_size(DESKTOP_VIEWPORT)
        await page.wait_for_timeout(500)  # let layout settle
        desktop_bytes = await page.screenshot(full_page=True, type="png")
        fact.screenshot_desktop_b64 = base64.b64encode(desktop_bytes).decode("ascii")

        # Screenshot mobile
        await page.set_viewport_size(MOBILE_VIEWPORT)
        await page.wait_for_timeout(500)
        mobile_bytes = await page.screenshot(full_page=True, type="png")
        fact.screenshot_mobile_b64 = base64.b64encode(mobile_bytes).decode("ascii")

        await browser.close()

    return fact


def run_visual_check(
    *,
    base_url: str | None = None,
    headless: bool = True,
    slow_mo: int = 0,
) -> VisualFact:
    """Synchronous entry point — runs the async Playwright check."""
    url = base_url or os.getenv("VISUAL_QA_BASE_URL", DEFAULT_BASE_URL)
    return asyncio.run(_run_playwright_visual_check(url, headed=not headless, slow_mo=slow_mo))


def save_visual_report(fact: VisualFact, run_dir: Path) -> Path:
    """Save screenshots + facts to run_dir/visual_qa/ and return the JSON path."""
    visual_dir = run_dir / "visual_qa"
    visual_dir.mkdir(parents=True, exist_ok=True)

    # Save screenshots as PNG files (easier to inspect)
    for name, b64 in [("desktop", fact.screenshot_desktop_b64), ("mobile", fact.screenshot_mobile_b64)]:
        if b64:
            png_path = visual_dir / f"screenshot_{name}.png"
            png_path.write_bytes(base64.b64decode(b64))

    # Save facts JSON (without the heavy base64 strings in the file)
    facts_dict = fact.to_dict()
    facts_dict.pop("screenshot_desktop_b64", None)
    facts_dict.pop("screenshot_mobile_b64", None)
    json_path = visual_dir / "facts.json"
    json_path.write_text(json.dumps(facts_dict, indent=2))

    return json_path


# CLI for manual testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run visual QA check against built app")
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="Base URL of the built app")
    parser.add_argument("--headed", action="store_true", help="Run headed (visible browser)")
    parser.add_argument("--slow-mo", type=int, default=0, help="Slow down Playwright (ms)")
    parser.add_argument("--output", type=Path, help="Directory to save screenshots + facts")
    args = parser.parse_args()

    print(f"[visual] Checking {args.url} ...", flush=True)
    fact = run_visual_check(base_url=args.url, headless=not args.headed, slow_mo=args.slow_mo)

    print(f"  map tiles: {fact.map_tile_count}")
    print(f"  start forms: {fact.start_form_count}")
    print(f"  end forms: {fact.end_form_count}")
    print(f"  top-card buttons: {fact.top_card_button_count}")
    print(f"  leftover labels: {fact.leftover_step_labels}")
    print(f"  console errors: {len(fact.console_errors)}")

    if args.output:
        save_visual_report(fact, args.output)
        print(f"  saved to {args.output}/visual_qa/")

    if fact.has_obvious_breakage():
        print("[visual] BLOCKED — obvious visual breakage detected", flush=True)
        sys.exit(1)
    else:
        print("[visual] PASS", flush=True)
        sys.exit(0)