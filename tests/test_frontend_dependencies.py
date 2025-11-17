# ruff: noqa: S101
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

env_file = ".test.gh.env" if os.getenv("GITHUB_ACTIONS") else ".test.env"
load_dotenv(Path("tests") / env_file)


COMFY_URL = os.getenv("COMFY_URL", "http://127.0.0.1:7960")
COMFY_TABS_CONTAINER_SELECTOR = ".workflow-tabs-container"
COMFY_ACTIVE_TAB_SELECTOR = ".p-togglebutton.p-component.p-togglebutton-checked .workflow-label"


def test_workflow_tabs_container_exists() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(COMFY_URL, wait_until="networkidle")

        tabs = page.locator(COMFY_TABS_CONTAINER_SELECTOR)
        assert tabs.count() > 0, "workflow-tabs-container missing"

        browser.close()


def test_active_workflow_tab_exists() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(COMFY_URL, wait_until="networkidle")

        active = page.locator(COMFY_ACTIVE_TAB_SELECTOR)
        assert active.count() > 0, "active workflow tab not found"

        browser.close()
