import json
import os
from collections.abc import Callable, Generator
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
import websocket
from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

from .workflows import SI1, SI3, SI4, SI5R

parent_path = Path(__file__).resolve().parent
env_file = ".test.gh.env" if os.getenv("GITHUB_ACTIONS") else ".test.env"


load_dotenv(parent_path / env_file)


COMFY_URL = os.getenv("COMFY_URL", "http://127.0.0.1:8188")


@pytest.fixture
def default_page() -> Generator[Page]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(COMFY_URL, wait_until="networkidle")
        yield page
        browser.close()


@pytest.fixture
def set_document_ids_func() -> Generator[Callable]:
    parsed_url = urlparse(COMFY_URL)
    ws_scheme = "wss" if parsed_url.scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{parsed_url.netloc}/ws"
    ws = websocket.create_connection(ws_url)

    data = json.loads(ws.recv())["data"]
    sid = data["sid"]

    def f(document_ids: list) -> None:
        url = f"{COMFY_URL}/krita/{sid}/documents"
        payload = {"documents": document_ids}
        response = requests.put(url, json=payload, timeout=1)
        response.raise_for_status()

    yield f
    ws.close()


@pytest.fixture
def si1_workflow(default_page: Page) -> Page:
    default_page.evaluate(
        f"""
            async () => {{
                const app = (await import('../../../scripts/app.js')).app;
                await app.loadGraphData({SI1});
            }}
            """,
    )
    return default_page


@pytest.fixture
def si3_workflow(default_page: Page) -> Page:
    default_page.evaluate(
        f"""
            async () => {{
                const app = (await import('../../../scripts/app.js')).app;
                await app.loadGraphData({SI3});
            }}
            """,
    )
    return default_page


@pytest.fixture
def si4_workflow(default_page: Page, set_document_ids_func: Callable) -> Page:
    set_document_ids_func(["banner", "badaboom"])
    default_page.evaluate(
        f"""
            async () => {{
                const app = (await import('../../../scripts/app.js')).app;
                await app.loadGraphData({SI4});
            }}
            """,
    )
    return default_page


@pytest.fixture
def si5r_workflow(default_page: Page, set_document_ids_func: Callable) -> Page:
    set_document_ids_func(["banner"])
    default_page.evaluate(
        f"""
            async () => {{
                const app = (await import('../../../scripts/app.js')).app;
                await app.loadGraphData({SI5R});
            }}
            """,
    )
    return default_page
