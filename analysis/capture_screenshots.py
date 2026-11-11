"""Capture the demo scenarios (test strategy §4) as PNGs for the presentation.

Start the GUI first (light theme, `.claude/launch.json`), then run:
    .venv/Scripts/python analysis/capture_screenshots.py [--base http://localhost:8501]
Drives the locally installed Chrome through Playwright (no browser download) and waits
until Streamlit has finished running before each screenshot.
"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "screenshots"
SHOTS = {
    "S01_AT-1_normal_day_80": "AT-1",
    "S02_AT-2_dark_model_decides": "AT-2",
    "S03_AT-3_black_ice_daylight": "AT-3",
    "S04a_AT-4_threshold_water_1000": "AT-4a",
    "S04b_AT-4_threshold_water_1001": "AT-4b",
    "S05_AT-5_poor_air_llm": "AT-5",
    "S06_AT-6_target_not_reachable": "AT-6",
    "S08_AT-8_most_restrictive_wins": "AT-8",
}


def _settle(page) -> None:
    page.wait_for_selector("text=Audit log", timeout=60_000)
    # the "running" status widget disappears when the script run is complete
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60_000)
    page.wait_for_timeout(1500)            # let charts finish drawing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8501")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1300}, color_scheme="light")
        page.goto(args.base)               # warm caches once
        _settle(page)
        for name, scenario in SHOTS.items():
            page.goto(f"{args.base}/?scenario={scenario}")
            _settle(page)
            png = OUT / f"{name}.png"
            page.screenshot(path=str(png), full_page=True)
            print(png.name, png.stat().st_size, "bytes")
        browser.close()


if __name__ == "__main__":
    main()
