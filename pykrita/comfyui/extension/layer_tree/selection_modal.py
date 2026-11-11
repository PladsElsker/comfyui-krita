from __future__ import annotations

from typing import Literal

from krita import Document, Node
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..models import KritaLayerType

SelectionMode = Literal["single", "multiple"]

SELECTABLE_LAYER_TYPES = {
    "paintlayer",
    "vectorlayer",
    "grouplayer",
    "filelayer",
    "filterlayer",
    "filllayer",
    "clonelayer",
    "referenceimageslayer",
}

THUMBNAIL_SIZE = 28


def iter_layer_nodes(parent: Node) -> list[Node]:
    """Return every descendant in Krita's bottom-to-top model order."""
    nodes: list[Node] = []
    for child in parent.childNodes():
        nodes.append(child)
        nodes.extend(iter_layer_nodes(child))
    return nodes


def index_layer_nodes(document: Document) -> dict[str, Node]:
    return {str(node.uniqueId()): node for node in iter_layer_nodes(document.rootNode())}


class LayerSelectionDialog(QDialog):
    """Shared hierarchy browser used by the Save Image and Load Image edit modes."""

    def __init__(
        self,
        document: Document,
        *,
        mode: SelectionMode,
        selected_ids: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.mode = mode
        self._selected_ids = set(selected_ids or [])
        self._nodes_by_id = index_layer_nodes(document)
        self._items_by_id: dict[str, QTreeWidgetItem] = {}

        self.setWindowTitle("Select Krita layer" if mode == "single" else "Select Krita layers")
        self.setMinimumSize(480, 540)
        self.resize(560, 680)

        layout = QVBoxLayout(self)
        description = QLabel(
            "Choose the layer where generated images will be inserted."
            if mode == "single"
            else "Choose the layers to composite and send to ComfyUI.",
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Filter layers…")
        self.search_input.textChanged.connect(self._filter_items)
        layout.addWidget(self.search_input)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(QPixmap(THUMBNAIL_SIZE, THUMBNAIL_SIZE).size())
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(
            QTreeWidget.SelectionMode.SingleSelection
            if mode == "single"
            else QTreeWidget.SelectionMode.ExtendedSelection
        )
        self.tree.itemDoubleClicked.connect(self._accept_on_double_click)
        layout.addWidget(self.tree, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_tree()
        self._restore_selection()

    def selected_nodes(self) -> list[Node]:
        selected_ids = {
            str(item.data(0, Qt.ItemDataRole.UserRole))
            for item in self.tree.selectedItems()
        }
        # Preserve the document's layer-stack order, independent of click order.
        return [
            node
            for node in iter_layer_nodes(self.document.rootNode())
            if str(node.uniqueId()) in selected_ids
        ]

    def accept(self) -> None:
        selected_nodes = self.selected_nodes()
        if not selected_nodes:
            self.search_input.setPlaceholderText("Select at least one layer to continue")
            self.tree.setFocus()
            return
        super().accept()

    def _populate_tree(self) -> None:
        for node in reversed(self.document.topLevelNodes()):
            self._add_node(node, self.tree.invisibleRootItem())

    def _add_node(self, node: Node, parent_item: QTreeWidgetItem) -> None:
        node_id = str(node.uniqueId())
        item = QTreeWidgetItem(parent_item)
        item.setText(0, node.name())
        item.setData(0, Qt.ItemDataRole.UserRole, node_id)
        item.setToolTip(0, f"{node.name()} — {node.type()}")
        item.setIcon(0, self._thumbnail_icon(node))
        selectable = self.mode == "single" or node.type() in SELECTABLE_LAYER_TYPES
        if not selectable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self._items_by_id[node_id] = item

        for child in reversed(node.childNodes()):
            self._add_node(child, item)

        if node.type() == "grouplayer":
            try:
                item.setExpanded(not node.collapsed())
            except RuntimeError:
                item.setExpanded(False)

    @staticmethod
    def _thumbnail_icon(node: Node) -> QIcon:
        try:
            thumbnail = node.thumbnail(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
            if thumbnail is not None and not thumbnail.isNull():
                return QIcon(QPixmap.fromImage(thumbnail))
        except (RuntimeError, TypeError):
            pass
        try:
            return node.icon()
        except (AttributeError, RuntimeError):
            return QIcon()

    def _restore_selection(self) -> None:
        for node_id in self._selected_ids:
            item = self._items_by_id.get(node_id)
            if item is not None and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                item.setSelected(True)
                self.tree.setCurrentItem(item)

    def _filter_items(self, text: str) -> None:
        query = text.casefold().strip()

        def update_visibility(item: QTreeWidgetItem) -> bool:
            child_matches = False
            for index in range(item.childCount()):
                child_matches = update_visibility(item.child(index)) or child_matches
            own_match = query in item.text(0).casefold()
            visible = not query or own_match or child_matches
            item.setHidden(not visible)
            if query and child_matches:
                item.setExpanded(True)
            return visible

        root = self.tree.invisibleRootItem()
        for index in range(root.childCount()):
            update_visibility(root.child(index))

    def _accept_on_double_click(self, _item: QTreeWidgetItem, _column: int) -> None:
        if self.selected_nodes():
            self.accept()


def select_layers(
    document: Document,
    *,
    mode: SelectionMode,
    selected_ids: list[str] | None = None,
    parent=None,
) -> list[Node] | None:
    dialog = LayerSelectionDialog(
        document,
        mode=mode,
        selected_ids=selected_ids,
        parent=parent,
    )
    if dialog.exec_() != QDialog.DialogCode.Accepted:
        return None
    return dialog.selected_nodes()
