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
            return app.graph !== undefined && app.graph !== null;
        }
        """,
    )
    assert app_graph is True, "app.graph is not defined"


def test__given_default_page_loaded__when_get_app_graph_nodes__then_app_graph_nodes_are_not_none(default_page: Page) -> None:
    app_graph = default_page.evaluate(
        """
        async () => {
            const app = (await import('../../../scripts/app.js')).app;
            return Array.isArray(app.graph?.nodes);
        }
        """,
    )
    assert app_graph is True, "app.graph.nodes is not defined"


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
            return workflow_actions_module.getInternalKritaNodes().length;
        }
        """,
    )
    assert internal_krita_nodes == 1, "expected exactly 1 internal krita node for si1 workflow"


def test__given_si3_workflow__when_get_internal_krita_nodes__then_3_nodes_are_returned(si3_workflow: Page) -> None:
    internal_krita_nodes = si3_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            return workflow_actions_module.getInternalKritaNodes().length;
        }
        """,
    )
    assert (
        internal_krita_nodes == SI3_AMOUNT_OF_INTERNAL_KRITA_NODES
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


def test__given_krita_output_node__when_krita_state_updates__then_metadata_widget_is_updated(si1_workflow: Page) -> None:
    updated_state = si1_workflow.evaluate(
        """
        async () => {
            const workflow_actions_module = await import('/extensions/comfyui-krita/workflow_actions.js');
            const node = workflow_actions_module.getInternalKritaNodes()[0];
            const document_widget = node.widgets.find(w => w.label === "document");
            const metadata_widget = node.widgets.find(w => w.label === "_meta-15347");

            document_widget.value = "krita-document-1";
            const state = {
                id: node.id,
                type: "KritaSaveImage-15347",
                document_id: "krita-document-1",
                insert_direction: "above",
                layer_name: "Background",
                path: [
                    { quuid: "layer-uuid", type: "target" }
                ]
            };

            workflow_actions_module.applyKritaNodeState(state);
            return JSON.parse(metadata_widget.value);
        }
        """,
    )

    assert updated_state["document_id"] == "krita-document-1"
    assert updated_state["insert_direction"] == "above"
    assert updated_state["path"] == [{"quuid": "layer-uuid", "type": "target"}]


def test__given_nested_subgraph__when_get_internal_krita_nodes__then_nested_node_is_found(
    default_page: Page,
) -> None:
    node_ids = default_page.evaluate(
        """
        async () => {
            const workflow = await import('/extensions/comfyui-krita/workflow_actions.js');
            const nestedGraph = { nodes: [] };
            const nestedKritaNode = { id: 42, type: "KritaSaveImage-15347" };
            nestedGraph.nodes.push(nestedKritaNode);
            const rootGraph = {
                nodes: [
                    { id: 1, type: "Reroute", subgraph: nestedGraph },
                    { id: 2, type: "Reroute", subgraph: nestedGraph },
                ]
            };
            nestedGraph.nodes.push({ id: 3, type: "Reroute", subgraph: nestedGraph });
            return workflow.getInternalKritaNodes(rootGraph).map(node => node.id);
        }
        """,
    )
    assert node_ids == [42], "nested Krita nodes should be found exactly once"


def test__given_nested_subgraph__when_fix_krita_node_ui__then_nested_metadata_widget_is_hidden(
    default_page: Page,
) -> None:
    metadata_widget = default_page.evaluate(
        """
        async () => {
            const workflow = await import('/extensions/comfyui-krita/workflow_actions.js');
            const metadataWidget = { label: "_meta-15347", hidden: false };
            const nestedNode = {
                type: "KritaSaveImage-15347",
                inputs: [{ name: "_meta-15347" }, { name: "document" }],
                widgets: [metadataWidget],
            };
            workflow.fixKritaNodeUi({
                type: "Reroute",
                subgraph: { nodes: [nestedNode] },
            });
            return {
                hidden: metadataWidget.hidden,
                remainingInputs: nestedNode.inputs.length,
            };
        }
        """,
    )
    assert metadata_widget == {"hidden": True, "remainingInputs": 0}


def test__given_krita_document_names__when_updating_document_widget_values__then_dynamic_combo_contains_selected_document(
    si1_workflow: Page,
) -> None:
    dropdown_state = si1_workflow.evaluate(
        """
        async () => {
            const workflow = await import('/extensions/comfyui-krita/workflow_actions.js');
            const node = workflow.getInternalKritaNodes()[0];
            await workflow.updateDocumentWidgetValues(["Unnamed"]);
            const dropdown = node.widgets.find(widget => widget.label === "document");
            return {
                options: dropdown.options.values,
                value: dropdown.value,
            };
        }
        """,
    )
    assert dropdown_state == {"options": ["Unnamed"], "value": "Unnamed"}


def test__given_krita_node__when_hiding_metadata_widget__then_widget_remains_serializable_but_not_visible(
    default_page: Page,
) -> None:
    metadata_state = default_page.evaluate(
        """
        async () => {
            const workflow = await import('/extensions/comfyui-krita/workflow_actions.js');
            const metadataWidget = {
                name: "_meta-15347",
                value: '{"document_id":"Unnamed"}',
                hidden: false,
                options: {},
            };
            const node = {
                type: "KritaSaveImage-15347",
                inputs: [{ name: "_meta-15347" }, { name: "document" }],
                widgets: [metadataWidget],
                setDirtyCanvas() {},
            };
            workflow.fixKritaNodeUi(node);
            return {
                hidden: metadataWidget.hidden,
                optionsHidden: metadataWidget.options.hidden,
                value: metadataWidget.value,
                remainingInputs: node.inputs.length,
            };
        }
        """,
    )
    assert metadata_state == {
        "hidden": True,
        "optionsHidden": True,
        "value": '{"document_id":"Unnamed"}',
        "remainingInputs": 0,
    }


def test__given_krita_output_node__when_metadata_input_is_created__then_metadata_widget_is_hidden(si1_workflow: Page) -> None:
    metadata_state = si1_workflow.evaluate(
        """
        async () => {
            const workflow = await import('/extensions/comfyui-krita/workflow_actions.js');
            const node = workflow.getInternalKritaNodes()[0];
            const widget = node.widgets.find(
                item => item.name === "_meta-15347" || item.label === "_meta-15347"
            );
            return {
                found: Boolean(widget),
                hidden: widget?.hidden ?? false,
                optionsHidden: widget?.options?.hidden ?? false,
            };
        }
        """,
    )
    assert metadata_state == {
        "found": True,
        "hidden": True,
        "optionsHidden": True,
    }


def test__given_krita_load_image_node__when_fix_krita_node_ui__then_document_and_metadata_widgets_are_hidden(
    default_page: Page,
) -> None:
    node_ui = default_page.evaluate(
        """
        async () => {
            const workflow = await import('/extensions/comfyui-krita/workflow_actions.js');
            const metadataWidget = {
                name: "_meta-15347",
                label: "_meta-15347",
                value: '{"document_id":"document-1"}',
                hidden: false,
                options: {},
            };
            const node = {
                id: 90,
                type: "KritaLoadImage-15347",
                inputs: [{ name: "_meta-15347" }, { name: "document" }],
                widgets: [
                    { name: "document", label: "document", value: "document-1" },
                    metadataWidget,
                ],
                setDirtyCanvas() {},
            };

            workflow.fixKritaNodeUi(node);
            return {
                isRegistered: workflow.KRITA_CUSTOM_IO_NODE_TYPES.includes(node.type),
                hidden: metadataWidget.hidden,
                optionsHidden: metadataWidget.options.hidden,
                remainingInputs: node.inputs.length,
                metadataValue: metadataWidget.value,
            };
        }
        """,
    )
    assert node_ui == {
        "isRegistered": True,
        "hidden": True,
        "optionsHidden": True,
        "remainingInputs": 0,
        "metadataValue": '{"document_id":"document-1"}',
    }


def test__given_krita_load_image_node__when_state_updates__then_input_metadata_widget_is_updated(
    default_page: Page,
) -> None:
    updated_state = default_page.evaluate(
        """
        async () => {
            const { app } = await import('../../../scripts/app.js');
            const workflow = await import('/extensions/comfyui-krita/workflow_actions.js');
            const node = {
                id: 99001,
                type: "KritaLoadImage-15347",
                inputs: [],
                widgets: [
                    { name: "document", label: "document", value: "document-1" },
                    { name: "_meta-15347", label: "_meta-15347", value: "" },
                ],
                setDirtyCanvas() {},
            };
            app.graph.nodes.push(node);

            workflow.applyKritaNodeState({
                id: 99001,
                type: "KritaLoadImage-15347",
                document_id: "document-1",
                layer_ids: ["layer-1", "layer-2"],
                layer_names: ["Background", "Line Art"],
                snapshot_revision: "revision-1",
            });

            const value = JSON.parse(node.widgets[1].value);
            app.graph.nodes.splice(app.graph.nodes.indexOf(node), 1);
            return value;
        }
        """,
    )
    assert updated_state == {
        "id": 99001,
        "type": "KritaLoadImage-15347",
        "document_id": "document-1",
        "layer_ids": ["layer-1", "layer-2"],
        "layer_names": ["Background", "Line Art"],
        "snapshot_revision": "revision-1",
    }



def test__given_both_krita_node_types__when_document_widgets_are_refreshed__then_both_use_the_same_document_ids(
    default_page: Page,
) -> None:
    dropdown_states = default_page.evaluate(
        """
        async () => {
            const { app } = await import('../../../scripts/app.js');
            const workflow = await import('/extensions/comfyui-krita/workflow_actions.js');
            const nodeTypes = ["KritaSaveImage-15347", "KritaLoadImage-15347"];
            const nodes = nodeTypes.map((type, index) => ({
                id: 70001 + index,
                type,
                inputs: [],
                widgets: [
                    {
                        name: "document",
                        label: "document",
                        value: null,
                        options: { values: [] },
                    },
                    {
                        name: "_meta-15347",
                        label: "_meta-15347",
                        value: "",
                        options: {},
                    },
                ],
                setDirtyCanvas() {},
            }));
            app.graph.nodes.push(...nodes);

            await workflow.updateDocumentWidgetValues(["document-1", "document-2"]);

            const result = nodes.map(node => {
                const dropdown = node.widgets[0];
                return {
                    type: node.type,
                    options: dropdown.options.values,
                    value: dropdown.value,
                };
            });
            app.graph.nodes.splice(
                app.graph.nodes.length - nodes.length,
                nodes.length,
            );
            return result;
        }
        """,
    )
    assert dropdown_states == [
        {
            "type": "KritaSaveImage-15347",
            "options": ["document-1", "document-2"],
            "value": "document-1",
        },
        {
            "type": "KritaLoadImage-15347",
            "options": ["document-1", "document-2"],
            "value": "document-1",
        },
    ]
