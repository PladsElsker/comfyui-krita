# ruff: noqa: S101
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page
from pydantic import BaseModel, RootModel, ValidationError

parent_path = Path(__file__).resolve().parent
env_file = ".test.gh.env" if os.getenv("GITHUB_ACTIONS") else ".test.env"


load_dotenv(parent_path / env_file)


SI3_AMOUNT_OF_KRITA_NODES = 3
SI3_AMOUNT_OF_INTERNAL_KRITA_NODES = 3
SI3_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP = 3
SI3_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP = 1
SI3_TOTAL_AMOUNT_OF_NODES = 4

SI4_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP = 2
SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BANNER = 2
SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BADABOOM = 2

SI5R_AMOUNT_OF_KRITA_NODES = 5


class Node(BaseModel):
    id: int
    type: str
    name: str


class DocumentIdsNodeMap(RootModel[dict[str, list[Node]]]):
    pass


def test__given_default_page_loaded__when_css_selecting_workflow_tabs_container__then_workflow_tabs_container_exists(default_page: Page) -> None:
    workflow_tabs_container = default_page.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return Array.from(document.querySelectorAll(workflow_actions_module.COMFY_TABS_CONTAINER_SELECTOR));
        }
        """,
    )
    assert len(workflow_tabs_container) > 0, "workflow-tabs-container missing"


def test__given_default_page_loaded__when_css_selecting_active_workflow_tab__then_active_workflow_tab_exists(default_page: Page) -> None:
    active_workflow_tab = default_page.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return Array.from(document.querySelectorAll(workflow_actions_module.COMFY_ACTIVE_TAB_SELECTOR));
        }
        """,
    )
    assert len(active_workflow_tab) > 0, "active workflow tab not found"


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
            return app.graph.nodes;
        }
        """,
    )
    assert app_graph is not None, "app.graph.nodes is not defined"


def test__given_si1_workflow__when_serialize_node__then_serialized_node_is_not_none(si1_workflow: Page) -> None:
    app_graph = si1_workflow.evaluate(
        """
        async () => {
            const app = (await import('../../../scripts/app.js')).app;
            return app.graph.nodes[0].serialize();
        }
        """,
    )
    assert app_graph is not None, "app.graph.serialized().nodes is not defined"


def test__given_si1_workflow__when_generate_active_krita_nodes__then_1_node_is_returned(si1_workflow: Page) -> None:
    custom_krita_nodes = si1_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.generateActiveKritaNodes();
        }
        """,
    )
    assert len(custom_krita_nodes) == 1, "the amount of nodes parsed should be 1"


def test__given_si3_workflow__when_generate_active_krita_nodes__then_3_nodes_are_returned(si3_workflow: Page) -> None:
    custom_krita_nodes = si3_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.generateActiveKritaNodes();
        }
        """,
    )
    assert len(custom_krita_nodes) == SI3_AMOUNT_OF_KRITA_NODES, f"the amount of nodes parsed should be {SI3_AMOUNT_OF_KRITA_NODES}"


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
    assert (
        len(internal_krita_nodes) == SI3_AMOUNT_OF_INTERNAL_KRITA_NODES
    ), f"expected exactly {SI3_AMOUNT_OF_INTERNAL_KRITA_NODES} internal krita nodes for si3 workflow"


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
        assert (
            len(document_map.root.keys()) == SI3_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP
        ), f"expected {SI3_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP} document id"
        assert (
            len(next(iter(document_map.root.values()))) == SI3_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP
        ), f"expected {SI3_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP} nodes"
    except ValidationError:
        pytest.fail("getDocumentIdsNodeMap() returned a bad model")


def test__given_si4_workflow__when_get_document_ids_node_map__then_map_contains_expected_structure(si4_workflow: Page) -> None:
    page = si4_workflow
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
        assert (
            len(document_map.root.keys()) == SI4_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP
        ), f"expected {SI4_AMOUNT_OF_DOCUMENT_IDS_IN_DOCUMENT_ID_MAP} document ids"
        assert all(
            document_id in document_map.root for document_id in ["banner", "badaboom"]
        ), "expected document ids 'banner' and 'badaboom' in the map"

        assert (
            len(document_map.root["banner"]) == SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BANNER
        ), f"expected {SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BANNER} nodes in 'banner'"
        assert (
            len(document_map.root["badaboom"]) == SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BADABOOM
        ), f"expected {SI4_AMOUNT_OF_NODES_IN_DOCUMENT_ID_MAP_UNDER_BADABOOM} nodes in 'badaboom'"
    except ValidationError:
        pytest.fail("getDocumentIdsNodeMap() returned a bad model")


def test__given_si4_workflow__when_modify_documents__then_document_ids_are_modified(si4_workflow: Page, set_document_ids_func: Callable) -> None:
    page = si4_workflow
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

    set_document_ids_func([])

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

    set_document_ids_func(["candy"])

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


def test__given_si5r_workflow__when_generate_active_krita_nodes__then_5_nodes_are_returned(si5r_workflow: Page) -> None:
    page = si5r_workflow

    nodes = page.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.generateActiveKritaNodes();
        }
        """,
    )
    assert len(nodes) == SI5R_AMOUNT_OF_KRITA_NODES, f"the amount of node pairs parsed should be {SI5R_AMOUNT_OF_KRITA_NODES}"


def test__given_si5r_workflow__when_modify_documents__then_document_ids_are_modified(si5r_workflow: Page, set_document_ids_func: Callable) -> None:
    page = si5r_workflow
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
        assert all(document_id in document_map.root for document_id in ["banner"]), "expected document id 'banner' in the map"
    except ValidationError:
        pytest.fail("getDocumentIdsNodeMap() returned a bad model")

    set_document_ids_func([])

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

    set_document_ids_func(["candy"])

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
