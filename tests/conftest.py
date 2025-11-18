# ruff: noqa: S101
import os
from pathlib import Path
import pytest

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

from .workflows import SI1, SI3, SI4

parent_path = Path(__file__).resolve().parent
env_file = ".test.gh.env" if os.getenv("GITHUB_ACTIONS") else ".test.env"


load_dotenv(parent_path / env_file)


COMFY_URL = os.getenv("COMFY_URL", "http://127.0.0.1:8188")


@pytest.fixture
def default_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(COMFY_URL, wait_until="networkidle")
        yield page
        browser.close()


@pytest.fixture
def si1_workflow(default_page: Page):
    default_page.evaluate(
        f"""
            async () => {{
                const app = (await import('../../../scripts/app.js')).app;
                await app.loadGraphData({SI1});
            }}
            """
    )
    yield default_page


@pytest.fixture
def si3_workflow(default_page: Page):
    default_page.evaluate(
        f"""
            async () => {{
                const app = (await import('../../../scripts/app.js')).app;
                await app.loadGraphData({SI3});
            }}
            """
    )
    yield default_page


# TODO:
# Before loading the graph data, create a websocket
# connection with the server, then send a request to
# "PUT /krita/{sid}/documents" with sids
# ["banner", "badaboom"] in the body.
# After yielding, close the websocket connection.
@pytest.fixture
def si4_workflow(default_page: Page):
    default_page.evaluate(
        f"""
            async () => {{
                const app = (await import('../../../scripts/app.js')).app;
                await app.loadGraphData({SI4});
            }}
            """
    )
    yield default_page
