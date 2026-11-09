import logging

from krita import Document, Node, View, Window
from PyQt5.QtCore import QItemSelectionModel, QModelIndex, QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QTreeView

from .utils import LayerUtils

LOGGER = logging.getLogger(__name__)


class TargetSelectionUnavailableError(RuntimeError):
    """Raised when Krita's Layers Docker cannot host a target-editing session."""


class LayerTargetPicker(QObject):
    """Temporarily uses Krita's Layers Docker to choose an output target.

    Public Krita APIs are used for active-document and active-node operations.
    The private Layers Docker tree view is isolated here because Krita does not
    expose a public setter for a multi-node layer selection.
    """

    target_selected = pyqtSignal(object)
    cancelled = pyqtSignal()

    def __init__(self, window: Window, document: Document, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.window = window
        self.document = document
        self._editing = False
        self._commit_scheduled = False
        self._view: View | None = None
        self._layer_view: QTreeView | None = None
        self._selection_model: QItemSelectionModel | None = None
        self._selection_connected = False
        self._active_view_connected = False
        self._previous_selection_ids: list[str] = []
        self._previous_active_node_id: str | None = None
        self._initial_target_id: str | None = None

    @property
    def is_editing(self) -> bool:
        return self._editing

    def begin(self, target: Node | None) -> None:
        if self._editing:
            message = "A target selection is already active"
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

        self._view = view
        self._layer_view = layer_view
        self._selection_model = selection_model
        self._previous_selection_ids = [str(node.uniqueId()) for node in view.selectedNodes()]
        active_node = self.document.activeNode()
        self._previous_active_node_id = str(active_node.uniqueId()) if active_node is not None else None
        self._initial_target_id = str(target.uniqueId()) if target is not None else None
        self._editing = True

        try:
            if target is not None:
                self.document.setActiveNode(target)
                target_index = self._index_for_node(target)
                selection_model.setCurrentIndex(target_index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                layer_view.scrollTo(target_index)

            selection_model.currentChanged.connect(self._schedule_commit)
            self._selection_connected = True
            self.window.activeViewChanged.connect(self._on_active_view_changed)
            self._active_view_connected = True
        except Exception:  # noqa: BLE001 - clean up the partial session, then re-raise
            try:
                self._finish(restore_selection=True)
            except Exception as cleanup_error:  # noqa: BLE001 - cleanup failure must remain visible
                message = "Target editing failed and the previous Krita selection could not be restored"
                raise RuntimeError(message) from cleanup_error
            raise

    def cancel(self) -> None:
        if not self._editing:
            return

        try:
            self._finish(restore_selection=True)
        finally:
            self.cancelled.emit()

    def _find_layer_view(self) -> QTreeView | None:
        # Krita's Layers Docker object name is private and intentionally kept here.
        for docker in self.window.dockers():
            layer_view = docker.findChild(QTreeView, "listLayers")
            if layer_view is not None:
                return layer_view

        return None

    def _on_active_view_changed(self, *_args: object) -> None:
        if self._editing and self.window.activeView() != self._view:
            # Do not apply the old document's selection to a different view.
            try:
                self._finish(restore_selection=False)
            finally:
                self.cancelled.emit()

    def _schedule_commit(self, *_args: object) -> None:
        if not self._editing or self._commit_scheduled:
            return

        self._commit_scheduled = True
        # Let Krita finish updating Document.activeNode() from the Docker event.
        QTimer.singleShot(0, self._commit_current_target)

    def _commit_current_target(self) -> None:
        self._commit_scheduled = False
        if not self._editing:
            return

        if self.window.activeView() != self._view or self._view.document() != self.document:
            try:
                self._finish(restore_selection=False)
            finally:
                self.cancelled.emit()
            return

        target = self.document.activeNode()
        if target is None or str(target.uniqueId()) == self._initial_target_id:
            return

        try:
            self._finish(restore_selection=True)
        except Exception:  # noqa: BLE001 - reset the UI signal state and propagate the failure
            self.cancelled.emit()
            raise

        self.target_selected.emit(target)

    def _finish(self, restore_selection: bool) -> None:
        try:
            if self._selection_connected:
                if self._selection_model is None:
                    message = "The Layers Docker selection model disappeared during target editing"
                    raise RuntimeError(message)
                self._selection_model.currentChanged.disconnect(self._schedule_commit)
                self._selection_connected = False

            if self._active_view_connected:
                self.window.activeViewChanged.disconnect(self._on_active_view_changed)
                self._active_view_connected = False

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
        nodes_by_id = {str(node.uniqueId()): node for node in LayerUtils.flatten_tree(self.document.topLevelNodes())}

        previous_active_node = nodes_by_id.get(self._previous_active_node_id)
        if self._previous_active_node_id is not None:
            if previous_active_node is None:
                LOGGER.warning("The previously active Krita layer was deleted before target editing finished")
            else:
                self.document.setActiveNode(previous_active_node)

        selection_model.clearSelection()
        missing_selection_ids = []

        for node_id in self._previous_selection_ids:
            node = nodes_by_id.get(node_id)
            if node is None:
                missing_selection_ids.append(node_id)
                continue

            index = self._index_for_node(node)
            selection_model.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)

        if missing_selection_ids:
            LOGGER.warning(
                "Could not restore %d previously selected Krita layer(s) because they were deleted: %s",
                len(missing_selection_ids),
                ", ".join(missing_selection_ids),
            )

        if previous_active_node is None:
            selection_model.setCurrentIndex(QModelIndex(), QItemSelectionModel.NoUpdate)
        else:
            active_index = self._index_for_node(previous_active_node)
            selection_model.setCurrentIndex(active_index, QItemSelectionModel.NoUpdate)

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

    def _clear_session(self) -> None:
        self._editing = False
        self._commit_scheduled = False
        self._view = None
        self._layer_view = None
        self._selection_model = None
        self._selection_connected = False
        self._active_view_connected = False
        self._previous_selection_ids = []
        self._previous_active_node_id = None
        self._initial_target_id = None
