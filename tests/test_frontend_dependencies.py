# ruff: noqa: S101
import os
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from playwright.sync_api import Page
from pydantic import BaseModel, RootModel, ValidationError
from websocket import WebSocket

from .conftest import COMFY_URL

parent_path = Path(__file__).resolve().parent
env_file = ".test.gh.env" if os.getenv("GITHUB_ACTIONS") else ".test.env"


load_dotenv(parent_path / env_file)


COMFY_TABS_CONTAINER_SELECTOR = ".workflow-tabs-container"
COMFY_ACTIVE_TAB_SELECTOR = ".p-togglebutton.p-component.p-togglebutton-checked .workflow-label"


SI3_AMOUNT_OF_KRITA_NODES = 3
SI3_AMOUNT_OF_INTERNAL_KRITA_NODES = 3
SI3_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP = 3
SI3_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP = 1
SI3_TOTAL_AMOUNT_OF_NODES = 4

SI4_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP = 2
SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BANNER = 2
SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BADABOOM = 2


class Node(BaseModel):
    id: int
    type: str
    name: str


class DocumentIdsNodeMap(RootModel[dict[str, list[Node]]]):
    pass


def test__given_default_page_loaded__when_css_selecting_workflow_tabs_container__then_workflow_tabs_container_exists(default_page: Page) -> None:
    tabs = default_page.locator(COMFY_TABS_CONTAINER_SELECTOR)
    assert tabs.count() > 0, "workflow-tabs-container missing"


def test__given_default_page_loaded__when_css_selecting_active_workflow_tab__then_active_workflow_tab_exists(default_page: Page) -> None:
    active = default_page.locator(COMFY_ACTIVE_TAB_SELECTOR)
    assert active.count() > 0, "active workflow tab not found"


def test__given_default_page_loaded__when_get_active_tab_name__then_active_tab_name_is_not_none(default_page: Page) -> None:
    tab_name = default_page.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getActiveTabName();
        }
        """,
    )
    assert tab_name is not None, "active workflow tab not found"


def test__given_default_page_loaded__when_get_app_graph__then_app_graph_is_not_none(default_page: Page) -> None:
    app_graph = default_page.evaluate(
        """
        async () => {
            const app = (await import('../../../scripts/app.js')).app;
            return app.graph;
        }
        """,
    )
    assert app_graph is not None, "app.graph is not defined"


def test__given_default_page_loaded__when_get_app_graph_nodes__then_app_graph_nodes_are_not_none(default_page: Page) -> None:
    app_graph = default_page.evaluate(
        """
        async () => {
            const app = (await import('../../../scripts/app.js')).app;
            return app.graph._nodes;
        }
        """,
    )
    assert app_graph is not None, "app.graph._nodes is not defined"


def test__given_default_page_loaded__when_serialize_graph__then_serialized_graph_nodes_are_not_none(default_page: Page) -> None:
    app_graph = default_page.evaluate(
        """
        async () => {
            const app = (await import('../../../scripts/app.js')).app;
            return app.graph.serialize().nodes;
        }
        """,
    )
    assert app_graph is not None, "app.graph.serialized().nodes is not defined"


def test__given_si1_workflow__when_generate_custom_krita_nodes__then_1_node_is_returned(si1_workflow: Page) -> None:
    custom_krita_nodes = si1_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.generateCustomKritaNodes();
        }
        """,
    )
    assert len(custom_krita_nodes) == 1, "the amount of nodes parsed should be 1"


def test__given_si3_workflow__when_generate_custom_krita_nodes__then_3_nodes_are_returned(si3_workflow: Page) -> None:
    custom_krita_nodes = si3_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.generateCustomKritaNodes();
        }
        """,
    )
    assert len(custom_krita_nodes) == SI3_AMOUNT_OF_KRITA_NODES, "the amount of nodes parsed should be 3"


def test__given_si3_workflow__when_get_node_pairs__then_4_tuples_are_returned(si3_workflow: Page) -> None:
    node_pairs = si3_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getNodePairs();
        }
        """,
    )
    assert len(node_pairs) == SI3_TOTAL_AMOUNT_OF_NODES, "the amount of node pairs parsed should be 4"


def test__given_si1_workflow__when_get_internal_krita_nodes__then_1_node_is_returned(si1_workflow: Page) -> None:
    internal_krita_nodes = si1_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getInternalKritaNodes();
        }
        """,
    )
    assert len(internal_krita_nodes) == 1, "expected exactly 1 internal krita node for si1 workflow"


def test__given_si3_workflow__when_get_internal_krita_nodes__then_3_nodes_are_returned(si3_workflow: Page) -> None:
    internal_krita_nodes = si3_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getInternalKritaNodes();
        }
        """,
    )
    assert len(internal_krita_nodes) == SI3_AMOUNT_OF_INTERNAL_KRITA_NODES, "expected exactly 3 internal krita nodes for si3 workflow"


def test__given_si3_workflow__when_get_document_ids_node_map__then_map_contains_expected_structure(si3_workflow: Page) -> None:
    document_map = si3_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getDocumentIdsNodeMap();
        }
        """,
    )

    try:
        document_map = DocumentIdsNodeMap.model_validate(document_map)
        assert len(document_map.root.keys()) == SI3_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP, "expected 1 document id"
        assert len(next(iter(document_map.root.values()))) == SI3_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP, "expected 3 nodes"
    except ValidationError:
        pytest.fail("getDocumentIdsNodeMap() returned a bad model")


def test__given_si4_workflow__when_get_document_ids_node_map__then_map_contains_expected_structure(si4_workflow: tuple[Page, WebSocket, str]) -> None:
    page, ws, sid = si4_workflow  # noqa: RUF059
    document_map = page.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getDocumentIdsNodeMap();
        }
        """,
    )

    try:
        document_map = DocumentIdsNodeMap.model_validate(document_map)
        assert len(document_map.root.keys()) == SI4_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP, "expected 2 document ids"
        assert all(
            document_id in document_map.root for document_id in ["banner", "badaboom"]
        ), "expected document ids 'banner' and 'badaboom' in the map"

        assert len(document_map.root["banner"]) == SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BANNER, "expected 2 nodes in 'banner'"
        assert len(document_map.root["badaboom"]) == SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BADABOOM, "expected 2 nodes in 'badaboom'"
    except ValidationError:
        pytest.fail("getDocumentIdsNodeMap() returned a bad model")


def test__given_si4_workflow__when_modify_documents__then_document_ids_are_modified(si4_workflow: tuple[Page, WebSocket, str]) -> None:
    page, ws, sid = si4_workflow  # noqa: RUF059
    document_map = page.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getDocumentIdsNodeMap();
        }
        """,
    )

    try:
        document_map = DocumentIdsNodeMap.model_validate(document_map)
        assert all(
            document_id in document_map.root for document_id in ["banner", "badaboom"]
        ), "expected document ids 'banner' and 'badaboom' in the map"
    except ValidationError:
        pytest.fail("getDocumentIdsNodeMap() returned a bad model")

    url = f"{COMFY_URL}/krita/{sid}/documents"
    payload = {"documents": []}
    response = requests.put(url, json=payload, timeout=1)
    response.raise_for_status()

    document_map = page.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getDocumentIdsNodeMap();
        }
        """,
    )

    try:
        document_map = DocumentIdsNodeMap.model_validate(document_map)
        assert all(document_id in document_map.root for document_id in ["null"]), "expected document id 'null' in the map"
    except ValidationError:
        pytest.fail("getDocumentIdsNodeMap() returned a bad model")

    url = f"{COMFY_URL}/krita/{sid}/documents"
    payload = {"documents": ["candy"]}
    response = requests.put(url, json=payload, timeout=1)
    response.raise_for_status()

    document_map = page.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getDocumentIdsNodeMap();
        }
        """,
    )

    try:
        document_map = DocumentIdsNodeMap.model_validate(document_map)
        assert all(document_id in document_map.root for document_id in ["candy"]), "expected document id 'candy' in the map"
    except ValidationError:
        pytest.fail("getDocumentIdsNodeMap() returned a bad model")
