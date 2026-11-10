import traceback

from krita import Document, Node
from PyQt5.QtCore import qWarning
from PyQt5.QtGui import QImage


def _warn(message: str, *args: object) -> None:
    """Send temporary diagnostics through Krita's Qt warning handler."""
    qWarning(message % args if args else message)


_MASK_NODE_TYPES = {
    "colormask",
    "colorizemask",
    "filtermask",
    "selectionmask",
    "transformmask",
    "transparencymask",
}


def capture_selected_layers_projection(
    document: Document,
    selected_nodes: list[Node],
) -> QImage:
    """Render selected layers through Krita's native projection renderer."""
    _warn(
        "[Load Image export] begin document=%r size=%dx%d model=%s depth=%s profile=%s selected=%s",
        document.name(),
        document.width(),
        document.height(),
        document.colorModel(),
        document.colorDepth(),
        document.colorProfile(),
        [(str(node.uniqueId()), node.name(), node.type()) for node in selected_nodes],
    )
    try:
        selected_roots = _get_selected_roots(document, selected_nodes)
        _warn(
            "[Load Image export] visible selected roots=%s",
            [(str(node.uniqueId()), node.name(), node.type()) for node in selected_roots],
        )

        keep_ids = _get_required_node_ids(selected_roots)
        _warn("[Load Image export] retained layer-tree nodes=%d", len(keep_ids))

        scratch_document = _clone_document(document)
        try:
            projection = _render_scratch_projection(scratch_document, keep_ids)
            _warn(
                "[Load Image export] projection ready size=%dx%d format=%s bytes_per_line=%d",
                projection.width(),
                projection.height(),
                projection.format(),
                projection.bytesPerLine(),
            )
            return projection
        finally:
            _warn("[Load Image export] closing scratch document")
            scratch_document.close()
    except Exception:
        _warn("[Load Image export] capture failed:\n%s", traceback.format_exc())
        raise


def _get_selected_roots(document: Document, selected_nodes: list[Node]) -> list[Node]:
    if not selected_nodes:
        message = "Select at least one Krita layer"
        raise ValueError(message)

    selected_ids = {str(node.uniqueId()) for node in selected_nodes}
    source_nodes = _nodes_by_id(document.rootNode())
    missing_ids = selected_ids - source_nodes.keys()
    if missing_ids:
        message = f"Selected Krita layers no longer exist: {', '.join(sorted(missing_ids))}"
        raise ValueError(message)

    roots = [node for node in selected_nodes if not _has_selected_ancestor(node, selected_ids) and _is_effectively_visible(node)]
    if not roots:
        message = "The selected layers are hidden or no longer available"
        raise ValueError(message)
    return roots


def _get_required_node_ids(selected_roots: list[Node]) -> set[str]:
    keep_ids: set[str] = set()
    for node in selected_roots:
        _add_subtree_ids(node, keep_ids)
        _add_ancestor_context_ids(node, keep_ids)
    return keep_ids


def _clone_document(document: Document) -> Document:
    _warn("[Load Image export] waiting for source document jobs")
    document.waitForDone()

    _warn("[Load Image export] acquiring source image barrier lock")
    document.lock()
    try:
        _warn("[Load Image export] cloning source document")
        scratch_document = document.clone()
    finally:
        document.unlock()
        _warn("[Load Image export] source image barrier lock released")

    if scratch_document is None:
        message = "Krita could not create an in-memory scratch document"
        raise RuntimeError(message)

    _warn(
        "[Load Image export] cloned document=%r size=%dx%d model=%s depth=%s profile=%s",
        scratch_document.name(),
        scratch_document.width(),
        scratch_document.height(),
        scratch_document.colorModel(),
        scratch_document.colorDepth(),
        scratch_document.colorProfile(),
    )
    return scratch_document


def _render_scratch_projection(
    scratch_document: Document,
    keep_ids: set[str],
) -> QImage:
    _warn("[Load Image export] configuring scratch document (batch mode)")
    scratch_document.setBatchmode(True)

    cloned_nodes = _nodes_by_id(scratch_document.rootNode())
    missing_ids = keep_ids - cloned_nodes.keys()
    if missing_ids:
        missing_ids_text = ", ".join(sorted(missing_ids))
        message = f"Krita's scratch document did not preserve selected layer identities: {missing_ids_text}"
        _warn(
            "[Load Image export] clone identity mismatch missing=%s cloned_count=%d cloned_ids=%s",
            sorted(missing_ids),
            len(cloned_nodes),
            sorted(cloned_nodes),
        )
        raise RuntimeError(message)

    hidden_nodes = []
    for node_id, node in cloned_nodes.items():
        if node_id not in keep_ids and node.visible():
            node.setVisible(False)
            hidden_nodes.append((node_id, node.name(), node.type()))

    _warn(
        "[Load Image export] visibility filtered hidden_count=%d retained_count=%d hidden=%s",
        len(hidden_nodes),
        len(keep_ids),
        hidden_nodes,
    )

    _warn("[Load Image export] waiting for scratch document visibility updates")
    scratch_document.waitForDone()

    _warn("[Load Image export] refreshing native projection")
    scratch_document.refreshProjection()

    width = scratch_document.width()
    height = scratch_document.height()
    _warn(
        "[Load Image export] reading projection rect=(0,0,%d,%d) model=%s depth=%s profile=%s",
        width,
        height,
        scratch_document.colorModel(),
        scratch_document.colorDepth(),
        scratch_document.colorProfile(),
    )
    projection = scratch_document.projection(0, 0, width, height)
    _warn(
        "[Load Image export] projection returned null=%s size=%dx%d format=%s",
        projection.isNull(),
        projection.width(),
        projection.height(),
        projection.format(),
    )
    if projection.isNull():
        message = "Krita returned an empty projection for the selected layers"
        raise RuntimeError(message)

    _warn("[Load Image export] copying projection out of scratch document")
    detached_projection = projection.copy()
    if detached_projection.isNull():
        message = "Krita could not detach the selected-layer projection from the scratch document"
        raise RuntimeError(message)

    return detached_projection


def _nodes_by_id(root: Node) -> dict[str, Node]:
    """Index the entire cloned layer tree, including Krita's root node."""
    nodes = [root, *_walk_nodes(root)]
    return {str(node.uniqueId()): node for node in nodes}


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


def _add_subtree_ids(node: Node, node_ids: set[str]) -> None:
    node_ids.add(str(node.uniqueId()))
    for child in node.childNodes():
        _add_subtree_ids(child, node_ids)


def _add_ancestor_context_ids(node: Node, node_ids: set[str]) -> None:
    parent = node.parentNode()
    while parent is not None:
        node_ids.add(str(parent.uniqueId()))
        for child in parent.childNodes():
            if child.type() in _MASK_NODE_TYPES:
                _add_subtree_ids(child, node_ids)
        parent = parent.parentNode()


def _is_effectively_visible(node: Node) -> bool:
    current: Node | None = node
    while current is not None:
        if not current.visible():
            return False
        current = current.parentNode()
    return True
