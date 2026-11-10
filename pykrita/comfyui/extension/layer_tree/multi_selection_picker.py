from contextlib import suppress

import logging

from krita import Document, Node, View, Window
from PyQt5.QtCore import QEvent, QItemSelectionModel, QModelIndex, QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication, QAbstractItemView, QTreeView

from .selection_session import (
    SelectionSessionUnavailableError as TargetSelectionUnavailableError,
    claim_selection_session,
    release_selection_session,
)

LOGGER = logging.getLogger(__name__)

SUPPORTED_LAYER_TYPES = {
    "paintlayer",
    "vectorlayer",
    "grouplayer",
    "filelayer",
    "filterlayer",
    "filllayer",
    "clonelayer",
    "referenceimageslayer",
}


class LayerMultiSelectionPicker(QObject):
    """Temporarily enables multi-selection in Krita's Layers Docker."""

    selection_accepted = pyqtSignal(object)
    cancelled = pyqtSignal()

    def __init__(self, window: Window, document: Document, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.window = window
        self.document = document
        self._editing = False
        self._view: View | None = None
        self._layer_view: QTreeView | None = None
        self._selection_model: QItemSelectionModel | None = None
        self._previous_selection_ids: list[str] = []
        self._previous_active_node_id: str | None = None
        self._previous_selection_mode: QAbstractItemView.SelectionMode | None = None
        self._event_filter_installed = False

    @property
    def is_editing(self) -> bool:
        return self._editing

    def begin(self, selected_ids: list[str] | None = None) -> None:
        if self._editing:
            message = "A layer selection is already active"
            raise RuntimeError(message)

        view = self.window.activeView()
        if view is None or view.document() != self.document:
            message = "The target document is not active"
            raise TargetSelectionUnavailableError(message)

        layer_view = self._find_layer_view()
        if layer_view is None:
            message = "Krita's Layers Docker is unavailable"
            raise TargetSelectionUnavailableError(message)

        selection_model = layer_view.selectionModel()
        if selection_model is None:
            message = "Krita's Layers Docker has no selection model"
            raise TargetSelectionUnavailableError(message)

        claim_selection_session(self)

        try:
            self._view = view
            self._layer_view = layer_view
            self._selection_model = selection_model
            # Snapshot only after the previous editor has restored its selection.
            self._previous_selection_ids = [str(node.uniqueId()) for node in view.selectedNodes()]
            active_node = self.document.activeNode()
            self._previous_active_node_id = str(active_node.uniqueId()) if active_node is not None else None
            self._previous_selection_mode = layer_view.selectionMode()
            self._editing = True

            layer_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            selection_model.clearSelection()
            selection_model.setCurrentIndex(QModelIndex(), QItemSelectionModel.SelectionFlag.NoUpdate)

            selected_id_set = set(selected_ids or [])
            selected_nodes = [
                node
                for node in self._walk_nodes(self.document.rootNode())
                if str(node.uniqueId()) in selected_id_set and node.type() in SUPPORTED_LAYER_TYPES
            ]
            for node in selected_nodes:
                index = self._index_for_node(node)
                selection_model.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                )

            if selected_nodes:
                current_index = self._index_for_node(selected_nodes[0])
                selection_model.setCurrentIndex(current_index, QItemSelectionModel.SelectionFlag.NoUpdate)
                layer_view.scrollTo(current_index)

            # Krita tracks the active node independently from the Qt selection
            # model. Clear the old single-layer active highlight as well as its
            # selection-model row before entering multi-selection mode.
            active_selection_node = selected_nodes[0] if selected_nodes else self.document.rootNode()
            self.document.setActiveNode(active_selection_node)

            self.window.activeViewChanged.connect(self._on_active_view_changed)
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
                self._event_filter_installed = True
        except Exception:
            if self._editing:
                self._finish(restore_selection=True)
            else:
                self._clear_session()
            raise

    def accept(self) -> list[Node]:
        if not self._editing:
            return []

        if self.window.activeView() != self._view or self._view is None or self._view.document() != self.document:
            self._finish(restore_selection=False)
            self.cancelled.emit()
            message = "The Krita document changed while selecting layers"
            raise TargetSelectionUnavailableError(message)

        selection_model = self._selection_model
        if selection_model is None:
            message = "The Layers Docker selection model disappeared during layer selection"
            raise RuntimeError(message)

        selected_indexes = selection_model.selectedRows(0)
        # Preserve the document's layer-stack order rather than the order in
        # which the user clicked rows.
        selected_nodes = [
            node
            for node in self._walk_nodes(self.document.rootNode())
            if node.type() in SUPPORTED_LAYER_TYPES and self._index_for_node(node) in selected_indexes
        ]
        if not selected_nodes:
            message = "Select at least one layer before accepting"
            raise ValueError(message)

        self._finish(restore_selection=True)
        self.selection_accepted.emit(selected_nodes)
        return selected_nodes

    def cancel(self) -> None:
        if not self._editing:
            return
        try:
            self._finish(restore_selection=True)
        finally:
            self.cancelled.emit()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if self._editing and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.cancel()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _find_layer_view(self) -> QTreeView | None:
        for docker in self.window.dockers():
            layer_view = docker.findChild(QTreeView, "listLayers")
            if layer_view is not None:
                return layer_view
        return None

    def _on_active_view_changed(self, *_args: object) -> None:
        if self._editing and self.window.activeView() != self._view:
            try:
                self._finish(restore_selection=False)
            finally:
                self.cancelled.emit()

    def _finish(self, restore_selection: bool) -> None:
        try:
            with suppress(TypeError, RuntimeError):
                self.window.activeViewChanged.disconnect(self._on_active_view_changed)

            if self._event_filter_installed:
                app = QApplication.instance()
                if app is not None:
                    app.removeEventFilter(self)
                self._event_filter_installed = False

            if self._layer_view is not None and self._previous_selection_mode is not None:
                self._layer_view.setSelectionMode(self._previous_selection_mode)
            if restore_selection:
                self._restore_selection()
        finally:
            self._clear_session()

    def _restore_selection(self) -> None:
        if self._layer_view is None or self.window.activeView() != self._view:
            LOGGER.warning("Skipped restoring the previous layer selection because its Krita view is no longer active")
            return
        view = self.window.activeView()
        if view is None or view.document() != self.document:
            LOGGER.warning("Skipped restoring the previous layer selection because its document is no longer active")
            return

        selection_model = self._layer_view.selectionModel()
        nodes_by_id = {str(node.uniqueId()): node for node in self._walk_nodes(self.document.rootNode())}
        previous_active_node = nodes_by_id.get(self._previous_active_node_id)
        if previous_active_node is not None:
            self.document.setActiveNode(previous_active_node)

        selection_model.clearSelection()
        for node_id in self._previous_selection_ids:
            node = nodes_by_id.get(node_id)
            if node is not None:
                index = self._index_for_node(node)
                selection_model.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                )

        if previous_active_node is None:
            selection_model.setCurrentIndex(QModelIndex(), QItemSelectionModel.SelectionFlag.NoUpdate)
        else:
            selection_model.setCurrentIndex(
                self._index_for_node(previous_active_node),
                QItemSelectionModel.SelectionFlag.NoUpdate,
            )

    def _index_for_node(self, node: Node) -> QModelIndex:
        layer_view = self._layer_view
        if layer_view is None:
            message = "The Layers Docker tree view is unavailable"
            raise RuntimeError(message)

        model = layer_view.model()
        root = self.document.rootNode()
        parent = node.parentNode()
        if parent is None or parent.uniqueId() == root.uniqueId():
            parent_index = QModelIndex()
            siblings = root.childNodes()
        else:
            parent_index = self._index_for_node(parent)
            layer_view.setExpanded(parent_index, expand=True)
            siblings = parent.childNodes()

        node_id = str(node.uniqueId())
        sibling_position = next(
            (index for index, sibling in enumerate(siblings) if str(sibling.uniqueId()) == node_id),
            None,
        )
        if sibling_position is None:
            message = f"Krita layer {node.name()!r} is not present among its parent's children"
            raise ValueError(message)

        # Krita's Node.childNodes() is bottom-to-top; the Docker displays top-to-bottom.
        row = len(siblings) - sibling_position - 1
        model_index = model.index(row, 0, parent_index)
        if not model_index.isValid():
            message = f"Could not resolve Krita layer {node.name()!r} in the Layers Docker"
            raise RuntimeError(message)
        return model_index

    @classmethod
    def _walk_nodes(cls, parent: Node) -> list[Node]:
        nodes: list[Node] = []
        for child in parent.childNodes():
            nodes.append(child)
            nodes.extend(cls._walk_nodes(child))
        return nodes

    def _clear_session(self) -> None:
        self._editing = False
        self._view = None
        self._layer_view = None
        self._selection_model = None
        self._previous_selection_ids = []
        self._previous_active_node_id = None
        self._previous_selection_mode = None
        release_selection_session(self)
