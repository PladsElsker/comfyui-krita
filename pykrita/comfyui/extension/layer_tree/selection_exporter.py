import logging
import os
import tempfile
import uuid
from pathlib import Path

from krita import Document, InfoObject, Node

from ..document_monitor import INTERNAL_DOCUMENT_NAME_PREFIX
from .multi_selection_picker import SUPPORTED_LAYER_TYPES

LOGGER = logging.getLogger(__name__)


def export_selected_layers(document: Document, selected_layer_ids: list[str]) -> bytes:
    """Export only selected layers, composited by Krita on a full-canvas clone."""
    selected_ids = set(selected_layer_ids)
    if not selected_ids:
        raise ValueError("Select at least one Krita layer")

    original_paths = _node_paths(document.rootNode())
    selected_paths = [path for node_id, path in original_paths.items() if node_id in selected_ids]
    if len(selected_paths) != len(selected_ids):
        missing = selected_ids - set(original_paths)
        raise ValueError(f"Some selected Krita layers no longer exist: {', '.join(sorted(missing))}")

    unsupported = [
        node_id
        for node_id in selected_ids
        if _node_type_for_id(document.rootNode(), node_id) not in SUPPORTED_LAYER_TYPES
    ]
    if unsupported:
        raise ValueError("One or more selected items are not image layers")

    clone = document.clone()
    if clone is None:
        raise RuntimeError("Krita could not create a temporary document clone")

    fd, temp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    Path(temp_path).unlink(missing_ok=True)

    try:
        clone.setName(f"{INTERNAL_DOCUMENT_NAME_PREFIX}{uuid.uuid4().hex}")
        clone.setAutosave(False)
        clone.setBatchmode(True)
        _hide_unselected_nodes(clone.rootNode(), (), selected_paths)

        clone.refreshProjection()
        clone.waitForDone()

        configuration = InfoObject()
        configuration.setProperty("alpha", True)
        configuration.setProperty("compression", 1)
        configuration.setProperty("forceSRGB", True)
        configuration.setProperty("indexed", False)
        configuration.setProperty("saveSRGBProfile", True)

        if not clone.exportImage(temp_path, configuration):
            raise RuntimeError("Krita could not export the selected layer composite as PNG")

        image_data = Path(temp_path).read_bytes()
        if not image_data:
            raise RuntimeError("Krita exported an empty layer composite")
        return image_data
    finally:
        Path(temp_path).unlink(missing_ok=True)
        try:
            clone.close()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Could not close the temporary Krita document clone")


def _node_paths(root: Node) -> dict[str, tuple[int, ...]]:
    result: dict[str, tuple[int, ...]] = {}

    def visit(parent: Node, parent_path: tuple[int, ...]) -> None:
        for index, child in enumerate(parent.childNodes()):
            path = parent_path + (index,)
            result[str(child.uniqueId())] = path
            visit(child, path)

    visit(root, ())
    return result


def _node_type_for_id(root: Node, node_id: str) -> str | None:
    remaining = list(root.childNodes())
    while remaining:
        node = remaining.pop()
        if str(node.uniqueId()) == node_id:
            return node.type()
        remaining.extend(node.childNodes())
    return None


def _hide_unselected_nodes(
    parent: Node,
    parent_path: tuple[int, ...],
    selected_paths: list[tuple[int, ...]],
) -> None:
    for index, node in enumerate(parent.childNodes()):
        path = parent_path + (index,)
        is_selected_or_ancestor = any(selected[: len(path)] == path for selected in selected_paths)
        is_selected_descendant = any(path[: len(selected)] == selected for selected in selected_paths)
        if not (is_selected_or_ancestor or is_selected_descendant):
            node.setVisible(False)
        _hide_unselected_nodes(node, path, selected_paths)
