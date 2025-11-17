# ruff: noqa: S101
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

parent_path = Path(__file__).resolve().parent
env_file = ".test.gh.env" if os.getenv("GITHUB_ACTIONS") else ".test.env"


load_dotenv(parent_path / env_file)


COMFY_URL = os.getenv("COMFY_URL", "http://127.0.0.1:8188")
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


def test_get_active_workflow_tab_name() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(COMFY_URL, wait_until="networkidle")

        tab_name = page.evaluate(
            """
            async () => {
                const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
                return workflow_actions_module.getActiveTabName();
            }
            """
        )
        assert tab_name == "Unsaved Workflow", "active workflow tab not found"

        browser.close()
