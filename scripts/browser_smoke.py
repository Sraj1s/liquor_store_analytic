"""Browser verification on CI, with screenshots retained as workflow artifacts."""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
os.chdir(root)
env = dict(os.environ, LIQUOR_DEMO="1", SQLITE_PATH="data/browser-demo.db")
for command in [
    ["generate", "--output", "data/raw/browser"],
    ["init", "--demo"],
    ["load", "--demo", "--input", "data/raw/browser"],
]:
    subprocess.run([sys.executable, "-m", "liquor.cli", *command], env=env, check=True)
output = root / "artifacts"
output.mkdir(exist_ok=True)
with (output / "streamlit.log").open("w") as log:
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "dashboard/app.py",
            "--server.headless=true",
            "--server.port=8501",
        ],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen(
                    "http://localhost:8501/_stcore/health", timeout=1
                ) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("Streamlit did not become healthy")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
            page.goto("http://localhost:8501", wait_until="networkidle")
            page.get_by_text("Daily sales and gross profit", exact=True).wait_for(timeout=30000)
            page.locator(".js-plotly-plot").first.wait_for(timeout=30000)
            assert page.locator('[data-testid="stException"]').count() == 0
            page.screenshot(path=str(output / "dashboard-sales.png"), full_page=True)
            with page.expect_download() as download:
                page.get_by_role("button", name="Download filtered sale items").click()
            file = Path(download.value.path())
            assert "revenue_cents" in file.read_text().splitlines()[0]
            page.get_by_role("tab", name="Inventory decisions").click()
            page.get_by_text("Restocking queue", exact=True).wait_for()
            page.screenshot(path=str(output / "dashboard-inventory.png"), full_page=True)
            page.get_by_role("tab", name="Pipeline health").click()
            page.get_by_text("Quarantined records", exact=True).wait_for()
            page.screenshot(path=str(output / "dashboard-pipeline.png"), full_page=True)
            assert page.locator('[data-testid="stException"]').count() == 0
            page.set_viewport_size({"width": 390, "height": 844})
            page.get_by_role("tab", name="Sales & profitability").click()
            page.screenshot(path=str(output / "dashboard-mobile.png"), full_page=True)
            browser.close()
        print("Browser smoke passed: three tabs, chart render, CSV download, mobile capture.")
    finally:
        server.terminate()
        server.wait(timeout=15)
