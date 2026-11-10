from krita import Document, Node
from PyQt5.QtCore import QRect

from .layer_compositor import LayerPixelSnapshot


def capture_selected_layer_pixels(
    document: Document,
    selected_nodes: list[Node],
) -> tuple[list[Node], int, int, list[LayerPixelSnapshot]]:
    """Copy only selected layer projections into detached, canvas-positioned buffers.

    Krita document/node access is intentionally kept on the caller (UI) thread.
    The returned byte buffers are independent copies suitable for worker-thread
    compositing.
    """
    selected_ids = {str(node.uniqueId()) for node in selected_nodes}
    if not selected_ids:
        raise ValueError("Select at least one Krita layer")

    document_width = document.width()
    document_height = document.height()
    if document_width <= 0 or document_height <= 0:
        raise ValueError("The Krita document has invalid canvas dimensions")

    # Use the document's bottom-to-top tree order, and avoid double-counting
    # selected descendants when their ancestor group is also selected.
    ordered_nodes = [
        node
        for node in _walk_nodes(document.rootNode())
        if str(node.uniqueId()) in selected_ids
    ]
    selected_node_ids = {str(node.uniqueId()) for node in ordered_nodes}
    filtered_nodes = [
        node
        for node in ordered_nodes
        if not _has_selected_ancestor(node, selected_node_ids)
    ]

    canvas = QRect(0, 0, document_width, document_height)
    snapshots: list[LayerPixelSnapshot] = []
    captured_nodes: list[Node] = []

    for node in filtered_nodes:
        if not _is_effectively_visible(node):
            continue

        if node.colorModel() != "RGBA" or node.colorDepth() != "U8":
            raise ValueError(
                f"Layer {node.name()!r} uses {node.colorModel()} {node.colorDepth()}. "
                "The current in-memory compositor requires RGBA U8 layer projections."
            )

        clipped_bounds = node.bounds().intersected(canvas)
        if clipped_bounds.isEmpty():
            continue

        x = clipped_bounds.x()
        y = clipped_bounds.y()
        width = clipped_bounds.width()
        height = clipped_bounds.height()
        pixel_data = bytes(node.projectionPixelData(x, y, width, height))
        expected_size = width * height * 4
        if len(pixel_data) != expected_size:
            raise RuntimeError(
                f"Krita returned {len(pixel_data)} bytes for layer {node.name()!r}; "
                f"expected {expected_size} RGBA bytes"
            )

        snapshots.append(
            LayerPixelSnapshot(
                name=node.name(),
                x=x,
                y=y,
                width=width,
                height=height,
                pixels=pixel_data,
                opacity=node.opacity(),
                blending_mode=node.blendingMode(),
            )
        )
        captured_nodes.append(node)

    if not snapshots:
        raise ValueError("The selected layers contain no visible pixels inside the document canvas")

    return captured_nodes, document_width, document_height, snapshots


def _walk_nodes(parent: Node) -> list[Node]:
    nodes: list[Node] = []
    for child in parent.childNodes():
        nodes.append(child)
        nodes.extend(_walk_nodes(child))
    return nodes


def _has_selected_ancestor(node: Node, selected_ids: set[str]) -> bool:
    parent = node.parentNode()
    while parent is not None:
        if str(parent.uniqueId()) in selected_ids:
            return True
        parent = parent.parentNode()
    return False


def _is_effectively_visible(node: Node) -> bool:
    current: Node | None = node
    while current is not None:
        if not current.visible():
            return False
        current = current.parentNode()
    return True
