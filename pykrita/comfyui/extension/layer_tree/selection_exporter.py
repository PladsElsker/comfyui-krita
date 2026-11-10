from krita import Document, Node
from PyQt5.QtGui import QImage


def capture_selected_layers_projection(
    document: Document,
    selected_nodes: list[Node],
) -> QImage:
    """Render the selected layer subtree through Krita's native image renderer.

    Krita objects must only be accessed from the UI thread. The returned QImage
    is detached from the scratch document and can be encoded on a worker thread.
    """
    if not selected_nodes:
        message = "Select at least one Krita layer"
        raise ValueError(message)

    selected_ids = {str(node.uniqueId()) for node in selected_nodes}
    source_nodes = _nodes_by_id(document.rootNode())
    missing_ids = selected_ids - source_nodes.keys()
    if missing_ids:
        message = f"Selected Krita layers no longer exist: {', '.join(sorted(missing_ids))}"
        raise ValueError(message)

    selected_roots = [
        node
        for node in selected_nodes
        if not _has_selected_ancestor(node, selected_ids) and _is_effectively_visible(node)
    ]
    if not selected_roots:
        message = "The selected layers are hidden or no longer available"
        raise ValueError(message)

    keep_ids: set[str] = set()
    for node in selected_roots:
        _add_subtree_ids(node, keep_ids)
        _add_ancestor_ids(node, keep_ids)

    # Krita's document clone is an independent in-memory image. Lock the source
    # while cloning so the copied node tree and its pixel data are consistent.
    document.waitForDone()
    if not document.tryBarrierLock():
        message = "Krita is still updating the document; try accepting the layer selection again"
        raise RuntimeError(message)

    scratch_document = None
    try:
        scratch_document = document.clone()
    finally:
        document.unlock()

    if scratch_document is None:
        message = "Krita could not create an in-memory scratch document"
        raise RuntimeError(message)

    try:
        cloned_nodes = _nodes_by_id(scratch_document.rootNode())
        if not keep_ids.issubset(cloned_nodes):
            message = "Krita's scratch document did not preserve the selected layer identities"
            raise RuntimeError(message)

        # Hide everything outside the selected subtrees. Ancestor groups remain
        # present so Krita can apply their own opacity, masks and blend behavior.
        for node_id, node in cloned_nodes.items():
            if node_id not in keep_ids and node.visible():
                node.setVisible(False)

        scratch_document.waitForDone()
        scratch_document.refreshProjection()
        projection = scratch_document.projection(
            0,
            0,
            scratch_document.width(),
            scratch_document.height(),
        )
        if projection.isNull():
            message = "Krita returned an empty projection for the selected layers"
            raise RuntimeError(message)

        return projection.copy()
    finally:
        scratch_document.close()


def _nodes_by_id(root: Node) -> dict[str, Node]:
    return {str(node.uniqueId()): node for node in _walk_nodes(root)}


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


def _add_ancestor_ids(node: Node, node_ids: set[str]) -> None:
    parent = node.parentNode()
    while parent is not None:
        node_ids.add(str(parent.uniqueId()))
        parent = parent.parentNode()


def _is_effectively_visible(node: Node) -> bool:
    current: Node | None = node
    while current is not None:
        if not current.visible():
            return False
        current = current.parentNode()
    return True
