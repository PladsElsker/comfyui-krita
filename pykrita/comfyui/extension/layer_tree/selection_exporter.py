from krita import Document, Node
from PyQt5.QtCore import QRect

from .layer_compositor import LayerGroupSnapshot, LayerPixelSnapshot


def capture_selected_layer_pixels(
    document: Document,
    selected_nodes: list[Node],
) -> tuple[int, int, list[LayerPixelSnapshot]]:
    """Copy only selected layer projections into detached, canvas-positioned buffers.

    This function must run on Krita's UI thread because it reads live document
    and Node objects. The returned snapshots contain only Python values and
    copied bytes; the compositor can safely consume them on a worker thread.
    """
    selected_ids = {str(node.uniqueId()) for node in selected_nodes}
    if not selected_ids:
        raise ValueError("Select at least one Krita layer")

    document_width = document.width()
    document_height = document.height()
    if document_width <= 0 or document_height <= 0:
        raise ValueError("The Krita document has invalid canvas dimensions")

    # Keep selected nodes in document tree order, not click order.
    ordered_nodes = [
        node
        for node in _walk_nodes(document.rootNode())
        if str(node.uniqueId()) in selected_ids
    ]
    if len(ordered_nodes) != len(selected_ids):
        found_ids = {str(node.uniqueId()) for node in ordered_nodes}
        missing = selected_ids - found_ids
        raise ValueError(f"Some selected Krita layers no longer exist: {', '.join(sorted(missing))}")

    # A selected group projection already includes its descendants and masks.
    # Drop selected descendants so that the group is only composited once.
    filtered_nodes = [
        node
        for node in ordered_nodes
        if not _has_selected_ancestor(node, selected_ids)
    ]

    canvas = QRect(0, 0, document_width, document_height)
    snapshots: list[LayerPixelSnapshot] = []

    for node in filtered_nodes:
        if not _is_effectively_visible(node):
            continue

        if node.colorModel() != "RGBA" or node.colorDepth() != "U8":
            raise ValueError(
                f"Layer {node.name()!r} uses {node.colorModel()} {node.colorDepth()}. "
                "The current in-memory compositor requires RGBA U8 projections."
            )

        clipped_bounds = node.bounds().intersected(canvas)
        if clipped_bounds.isEmpty():
            continue

        x = clipped_bounds.x()
        y = clipped_bounds.y()
        width = clipped_bounds.width()
        height = clipped_bounds.height()
        # projectionPixelData returns a QByteArray copy of rendered pixels.
        # bytes() detaches it from Krita before this method returns.
        pixel_data = bytes(node.projectionPixelData(x, y, width, height))
        expected_size = width * height * 4
        if len(pixel_data) != expected_size:
            raise RuntimeError(
                f"Krita returned {len(pixel_data)} bytes for layer {node.name()!r}; "
                f"expected {expected_size} RGBA bytes"
            )

        ancestors = _group_ancestors(node)
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
                ancestors=ancestors,
            )
        )

    if not snapshots:
        raise ValueError("The selected layers contain no visible pixels inside the document canvas")

    return document_width, document_height, snapshots


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


def _group_ancestors(node: Node) -> tuple[LayerGroupSnapshot, ...]:
    ancestors: list[LayerGroupSnapshot] = []
    parent = node.parentNode()
    while parent is not None:
        if parent.type() == "grouplayer":
            ancestors.append(
                LayerGroupSnapshot(
                    node_id=str(parent.uniqueId()),
                    opacity=parent.opacity(),
                    blending_mode=parent.blendingMode(),
                )
            )
        parent = parent.parentNode()

    ancestors.reverse()
    return tuple(ancestors)


def _is_effectively_visible(node: Node) -> bool:
    current: Node | None = node
    while current is not None:
        if not current.visible():
            return False
        current = current.parentNode()
    return True
