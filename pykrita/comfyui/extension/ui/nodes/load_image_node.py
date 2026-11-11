import hashlib
import logging
import uuid
from typing import ClassVar, cast

from krita import DockWidget, Document, Node as KritaNode, Window
from PyQt5.QtCore import (
    QTimer,
    QByteArray,
    QSize,
    QBuffer,
    QIODevice,
    Qt,
    QRunnable,
    QThreadPool,
    pyqtBoundSignal,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import QIcon, QImage, QPalette
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QToolButton

from comfyui.extension.layer_tree.selection_exporter import capture_selected_layers_projection
from comfyui.extension.layer_tree.document_change_tracker import document_change_tracker
from comfyui.extension.layer_tree.selection_modal import iter_layer_nodes, select_layers
from comfyui.extension.models import LoadImageState, Node, UiNodeState
from comfyui.extension.ui.icons import (
    STACKS_ICON,
    render_svg_to_pixmap,
)
from comfyui.extension.ui.micro.buttons import TargetEditButton

from .comfyui_node import ComfyUiNode

LOGGER = logging.getLogger(__name__)


def _walk_layer_tree(parent: KritaNode) -> list[KritaNode]:
    nodes: list[KritaNode] = []
    for child in parent.childNodes():
        nodes.append(child)
        nodes.extend(_walk_layer_tree(child))
    return nodes


MAX_EXPORT_PLACEHOLDER_PIXELS = 16_000_000


class _ProjectionExportSignals(QObject):
    completed = cast("pyqtBoundSignal", pyqtSignal(object, object, object, bytes))
    failed = cast("pyqtBoundSignal", pyqtSignal(object, object, str))
    scratch_document_ready = cast("pyqtBoundSignal", pyqtSignal(object))


class _ScratchDocumentDisposer(QObject):
    @pyqtSlot(object)
    def dispose(self, document: Document) -> None:
        # Scratch documents are created in the worker but Krita's QObject
        # document wrapper is disposed from the GUI thread.
        try:
            document.close()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Could not close a Load Image scratch document")


_SCRATCH_DOCUMENT_DISPOSER = _ScratchDocumentDisposer()


def _encode_projection_png(projection: QImage) -> bytes:
    buffer_data = QByteArray()
    buffer = QBuffer(buffer_data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        message = "Could not open the in-memory PNG buffer"
        raise RuntimeError(message)

    try:
        if not projection.save(buffer, "PNG"):
            message = "Krita could not encode the selected-layer projection as PNG"
            raise RuntimeError(message)
        image_data = bytes(buffer_data)
    finally:
        buffer.close()

    if not image_data:
        message = "Krita produced an empty PNG for the selected layers"
        raise RuntimeError(message)
    return image_data


def _create_transparent_black_projection(dimensions: tuple[int, int] | None) -> QImage:
    if dimensions is None:
        message = "The blank Load Image preview requires document dimensions"
        raise ValueError(message)

    width, height = dimensions
    if width < 1 or height < 1 or width * height > MAX_EXPORT_PLACEHOLDER_PIXELS:
        message = "The Krita document dimensions exceed the supported Load Image preview size"
        raise ValueError(message)

    projection = QImage(width, height, QImage.Format.Format_RGBA8888)
    if projection.isNull():
        message = "Krita could not allocate the blank Load Image preview"
        raise RuntimeError(message)

    # Zero RGBA bytes represent black RGB with fully transparent alpha.
    projection.fill(0)
    return projection


class _ProjectionExportTask(QRunnable):
    def __init__(
        self,
        document: Document,
        state: LoadImageState,
        selected_layer_ids: list[str],
        capture_token: str,
        blank_dimensions: tuple[int, int] | None = None,
    ) -> None:
        super().__init__()
        self.document = document
        self.state = state
        self.selected_layer_ids = list(selected_layer_ids)
        self.capture_token = capture_token
        self.blank_dimensions = blank_dimensions
        self.signals = _ProjectionExportSignals()
        self.signals.scratch_document_ready.connect(
            _SCRATCH_DOCUMENT_DISPOSER.dispose,
            Qt.ConnectionType.QueuedConnection,
        )

    def run(self) -> None:
        scratch_document: Document | None = None
        try:
            if self.selected_layer_ids:
                projection, scratch_document = capture_selected_layers_projection(
                    self.document,
                    self.selected_layer_ids,
                )
                self.signals.scratch_document_ready.emit(scratch_document)
            else:
                projection = _create_transparent_black_projection(self.blank_dimensions)

            revision = _projection_revision(projection)
            state = self.state.model_copy(
                update={"snapshot_revision": revision, "snapshot_pending": False},
            )

            image_data = _encode_projection_png(projection)
            self.signals.completed.emit(self, self.capture_token, state, image_data)
        except Exception as error:  # noqa: BLE001
            if scratch_document is None:
                scratch_document = getattr(error, "scratch_document", None)
                if scratch_document is not None:
                    self.signals.scratch_document_ready.emit(scratch_document)
            self.signals.failed.emit(self, self.capture_token, str(error))


def _projection_revision(projection: QImage) -> str:
    normalized = projection.convertToFormat(QImage.Format.Format_RGBA8888)
    byte_count = normalized.bytesPerLine() * normalized.height()
    pixel_buffer = normalized.bits()
    pixel_buffer.setsize(byte_count)

    digest = hashlib.sha256()
    digest.update(normalized.width().to_bytes(4, "big"))
    digest.update(normalized.height().to_bytes(4, "big"))
    digest.update(bytes(pixel_buffer))
    return digest.hexdigest()


class LoadImageNode(ComfyUiNode):
    type: ClassVar[str] = "KritaLoadImage-15347"
    snapshot_ready = cast("pyqtBoundSignal", pyqtSignal(object, bytes))
    LIVE_REFRESH_DEBOUNCE_MS: ClassVar[int] = 450

    def __init__(
        self,
        docker: DockWidget,
        node: Node,
        window: Window,
        document: Document,
        document_id: str,
    ) -> None:
        super().__init__(docker, node, STACKS_ICON, document_id)
        self.setObjectName("LoadImageNode")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, on=True)
        self._configure_layer_edit_style()
        self.window = window
        self.document = document
        self.layer_ids: list[str] = []
        self.layer_names: list[str] = []
        self.snapshot_revision = ""
        self.snapshot_pending = False
        self.placeholder = False
        self.selection_generation = 0
        self._pending_state: LoadImageState | None = None
        self._composition_pool = QThreadPool.globalInstance()
        self._composition_tasks: set[_ProjectionExportTask] = set()
        self._capture_active = False
        self._active_capture_token: str | None = None
        self._latest_capture: tuple[str, list[str], list[str]] | None = None
        self._refresh_requested = False
        self._disposed = False
        self._live_refresh_timer = QTimer(self)
        self._live_refresh_timer.setSingleShot(True)
        self._live_refresh_timer.setInterval(self.LIVE_REFRESH_DEBOUNCE_MS)
        self._live_refresh_timer.timeout.connect(self._refresh_selected_projection)
        self._modal_active = False
        self._change_tracker = document_change_tracker()

        self.set_title_text(node.name)
        self._update_layer_info()

        self.edit_button = TargetEditButton()
        self.edit_button.setToolTip("Select layers")
        self.edit_button.clicked.connect(self._toggle_editing)
        self.set_action_buttons([self.edit_button])

        # One application-wide tracker coalesces input for all nodes targeting
        # this document. The modal itself never changes Krita's native selection.
        self._change_tracker.watch(document, window, self, self._on_document_changed)

    def _create_action_button(self, icon_renderer: QSvgRenderer, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setAutoRaise(True)
        button.setContentsMargins(0, 0, 0, 0)
        button.setToolTip(tooltip)

        color = button.palette().color(QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(icon_renderer, size=QSize(20, 20), color=color)
        if pixmap:
            button.setIconSize(pixmap.size())
            button.setIcon(QIcon(pixmap))

        return button

    def initialize_state(self) -> None:
        if self.layer_ids or self.snapshot_revision or self.snapshot_pending:
            return
        self._queue_projection_capture([], [])

    def cleanup(self) -> None:
        self._disposed = True
        self._latest_capture = None
        self._live_refresh_timer.stop()
        self._change_tracker.unwatch(self.document, self)
        self.set_action_buttons([])
        self.edit_button.hide()
        self.edit_button.setEnabled(False)
        self.edit_button.setParent(None)
        self.edit_button.deleteLater()
        self._pending_state = None

    def apply(self, node_state: UiNodeState) -> None:
        self._apply_state(cast("LoadImageState", node_state))

    def _apply_state(self, state: LoadImageState) -> None:
        self.layer_ids = list(state.layer_ids)
        self.layer_names = list(state.layer_names)
        self.snapshot_revision = state.snapshot_revision
        self.snapshot_pending = state.snapshot_pending
        self.placeholder = state.placeholder
        self.selection_generation = state.selection_generation
        self._update_layer_info()

    def _toggle_editing(self, _checked: bool) -> None:
        if self._modal_active or self._disposed:
            return

        self._modal_active = True
        self._set_layer_editing_feedback(editing=True)
        try:
            selected_nodes = select_layers(
                self.document,
                mode="multiple",
                selected_ids=self.layer_ids,
                allow_empty=True,
                parent=self,
            )
            if selected_nodes is not None:
                self._selection_accepted(selected_nodes)
        finally:
            self._modal_active = False
            self._set_layer_editing_feedback(editing=False)

    def _selection_accepted(self, selected_nodes: list[KritaNode]) -> None:
        layer_ids = [str(layer.uniqueId()) for layer in selected_nodes]
        layer_names = [layer.name() for layer in selected_nodes]
        self._queue_projection_capture(layer_ids, layer_names)

    def _update_layer_info(self) -> None:
        layer_count = len(self.layer_ids)
        label = "layer" if layer_count == 1 else "layers"
        self.set_info_text(f"{layer_count} {label} selected")

    def _configure_layer_edit_style(self) -> None:
        self.setStyleSheet(
            'QWidget#LoadImageNode[layerEditing="true"] {'
            "border: 1px solid #D6A000;"
            "border-radius: 5px;"
            "background-color: rgba(255, 205, 64, 58);"
            "}"
        )
        self.setProperty("layerEditing", False)  # noqa: FBT003

    def _set_layer_editing_feedback(self, *, editing: bool) -> None:
        self.setProperty("layerEditing", editing)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _on_document_changed(self) -> None:
        if self._disposed:
            return

        nodes_by_id = {
            str(node.uniqueId()): node
            for node in iter_layer_nodes(self.document.rootNode())
        }
        remaining_ids = [layer_id for layer_id in self.layer_ids if layer_id in nodes_by_id]
        remaining_names = [nodes_by_id[layer_id].name() for layer_id in remaining_ids]
        selection_changed = remaining_ids != self.layer_ids or remaining_names != self.layer_names

        if selection_changed:
            self._queue_projection_capture(remaining_ids, remaining_names)
        elif self.layer_ids:
            self._schedule_live_refresh()

    def _schedule_live_refresh(self) -> None:
        if not self.layer_ids or self.layer_picker.is_editing:
            return
        self._live_refresh_timer.start()

    def _refresh_selected_projection(self) -> None:
        if not self.layer_ids or self.layer_picker.is_editing or self._disposed:
            return
        self._queue_projection_capture(self.layer_ids, self.layer_names)

    def _selection_accepted(self, selected_nodes: list[KritaNode]) -> None:
        self._reset_edit_controls()
        layer_ids = [str(layer.uniqueId()) for layer in selected_nodes]
        layer_names = [layer.name() for layer in selected_nodes]
        self._queue_projection_capture(layer_ids, layer_names)

    def _queue_projection_capture(self, layer_ids: list[str], layer_names: list[str]) -> None:
        if self._disposed:
            return

        # Keep only the latest requested layer set. A running render is never
        # duplicated; a newer request is processed as soon as it completes.
        self.selection_generation += 1
        self.layer_ids = list(layer_ids)
        self.layer_names = list(layer_names)
        self._update_layer_info()
        self._pending_state = None

        if not layer_ids:
            self._active_capture_token = None
            self._refresh_requested = False
            self._live_refresh_timer.stop()

        pending_state = LoadImageState(
            id=self.id,
            type=self.type,
            document_id=self.document_id,
            layer_ids=list(layer_ids),
            layer_names=list(layer_names),
            snapshot_revision=self.snapshot_revision,
            selection_generation=self.selection_generation,
            snapshot_pending=True,
            placeholder=not layer_ids,
        )
        self.snapshot_pending = True
        self.placeholder = not layer_ids
        self.state_changed.emit(pending_state)
        self._latest_capture = (uuid.uuid4().hex, list(layer_ids), list(layer_names))
        self._refresh_requested = True
        self._start_latest_projection_capture()

    def _start_latest_projection_capture(self) -> None:
        if self._disposed or self._capture_active or self._pending_state is not None or self._latest_capture is None:
            return

        capture_token, layer_ids, layer_names = self._latest_capture
        self._latest_capture = None
        state = LoadImageState(
            id=self.id,
            type=self.type,
            document_id=self.document_id,
            layer_ids=layer_ids,
            layer_names=layer_names,
            snapshot_revision=self.snapshot_revision,
            selection_generation=self.selection_generation,
            snapshot_pending=True,
            placeholder=not layer_ids,
        )
        blank_dimensions = None
        if not layer_ids:
            blank_dimensions = (self.document.width(), self.document.height())
        task = _ProjectionExportTask(
            self.document,
            state,
            layer_ids,
            capture_token,
            blank_dimensions=blank_dimensions,
        )
        task.signals.completed.connect(
            self._on_projection_export_completed,
            Qt.ConnectionType.QueuedConnection,
        )
        task.signals.failed.connect(
            self._on_projection_export_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        self._capture_active = True
        self._active_capture_token = capture_token
        self._composition_tasks.add(task)
        self._update_layer_info()
        self._composition_pool.start(task)

    def _on_projection_export_completed(
        self,
        task: _ProjectionExportTask,
        capture_token: str,
        state: LoadImageState,
        image_data: bytes,
    ) -> None:
        self._composition_tasks.discard(task)
        active_token = self._active_capture_token
        self._capture_active = False
        self._active_capture_token = None

        if self._disposed:
            return
        if capture_token != active_token or self._latest_capture is not None:
            self._start_latest_projection_capture()
            return

        if state.snapshot_revision == self.snapshot_revision:
            # Selection metadata may change while composed pixels remain equal.
            self._apply_state(state)
            self._pending_state = None
            self.state_changed.emit(state)
            self._update_layer_info()
            self._refresh_requested = False
            self._start_latest_projection_capture()
            return

        self._pending_state = state
        self._refresh_requested = False
        self._update_layer_info()
        self.snapshot_ready.emit(state, image_data)

    def _on_projection_export_failed(
        self,
        task: _ProjectionExportTask,
        capture_token: str,
        error: str,
    ) -> None:
        self._composition_tasks.discard(task)
        active_token = self._active_capture_token
        self._capture_active = False
        self._active_capture_token = None

        if self._disposed:
            return
        if capture_token != active_token or self._latest_capture is not None:
            self._start_latest_projection_capture()
            return

        self._update_layer_info()
        LOGGER.error("Could not export the selected Krita layer projection: %s", error)
        self._refresh_requested = False
        self._start_latest_projection_capture()

    def snapshot_uploaded(self, state: LoadImageState) -> None:
        if (
            self._pending_state is None
            or self._pending_state.snapshot_revision != state.snapshot_revision
            or self._pending_state.selection_generation != state.selection_generation
            or self._pending_state.placeholder != state.placeholder
        ):
            return

        self._pending_state = None
        if self._latest_capture is not None:
            # The tree changed while this older upload was in flight. Keep the
            # newer selected IDs/count and publish only the newest projection.
            self._start_latest_projection_capture()
            return

        self._apply_state(state)
        self.state_changed.emit(state)
        self._start_latest_projection_capture()

    def snapshot_upload_failed(self, state: LoadImageState, error: str) -> None:
        if (
            self._pending_state is None
            or self._pending_state.snapshot_revision != state.snapshot_revision
            or self._pending_state.selection_generation != state.selection_generation
            or self._pending_state.placeholder != state.placeholder
        ):
            return

        self._pending_state = None
        self._update_layer_info()
        LOGGER.error("Could not upload the Krita layer snapshot: %s", error)
        self._start_latest_projection_capture()

    def _update_layer_info(self) -> None:
        layer_count = len(self.layer_ids)
        label = "layer" if layer_count == 1 else "layers"
        self.set_info_text(f"{layer_count} {label} selected")
