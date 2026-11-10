import hashlib
import logging
import traceback
from typing import ClassVar, cast

from krita import DockWidget, Document, Node as KritaNode, Window
from PyQt5.QtCore import (
    QEvent,
    QTimer,
    qWarning,
    QByteArray,
    QSize,
    QBuffer,
    QIODevice,
    QObject,
    Qt,
    QRunnable,
    QThreadPool,
    pyqtBoundSignal,
    pyqtSignal,
)
from PyQt5.QtGui import QIcon, QImage, QPalette
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication, QToolButton, QWidget

from comfyui.extension.layer_tree.multi_selection_picker import LayerMultiSelectionPicker
from comfyui.extension.layer_tree.selection_exporter import capture_selected_layers_projection
from comfyui.extension.layer_tree.target_picker import TargetSelectionUnavailableError
from comfyui.extension.models import LoadImageState, Node, UiNodeState
from comfyui.extension.ui.icons import (
    CANCEL_ICON,
    CHECK_ICON,
    STACKS_ICON,
    render_svg_to_pixmap,
)
from comfyui.extension.ui.micro.buttons import TargetEditButton

from .comfyui_node import ComfyUiNode

LOGGER = logging.getLogger(__name__)


class _ProjectionExportSignals(QObject):
    completed = cast("pyqtBoundSignal", pyqtSignal(object, object, bytes))
    failed = cast("pyqtBoundSignal", pyqtSignal(object, object, str))


class _ProjectionExportTask(QRunnable):
    def __init__(self, state: LoadImageState, projection: QImage) -> None:
        super().__init__()
        self.state = state
        self.projection = projection
        self.signals = _ProjectionExportSignals()

    def run(self) -> None:
        buffer_data = QByteArray()
        buffer = QBuffer(buffer_data)
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            message = "Could not open the in-memory PNG buffer"
            self.signals.failed.emit(self, self.state, message)
            return

        try:
            if not self.projection.save(buffer, "PNG"):
                message = "Krita could not encode the selected-layer projection as PNG"
                self.signals.failed.emit(self, self.state, message)
                return
            image_data = bytes(buffer_data)
        except Exception as error:  # noqa: BLE001
            self.signals.failed.emit(self, self.state, str(error))
            return
        finally:
            buffer.close()

        if not image_data:
            message = "Krita produced an empty PNG for the selected layers"
            self.signals.failed.emit(self, self.state, message)
            return

        self.signals.completed.emit(self, self.state, image_data)


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
    CANVAS_WIDGET_TYPES: ClassVar[set[str]] = {"KisOpenGLCanvas2", "KisQPainterCanvas"}
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
        self.window = window
        self.document = document
        self.layer_ids: list[str] = []
        self.layer_names: list[str] = []
        self.snapshot_revision = ""
        self._pending_state: LoadImageState | None = None
        self._composition_pool = QThreadPool.globalInstance()
        self._composition_tasks: set[_ProjectionExportTask] = set()
        self._refresh_requested = False
        self._live_refresh_timer = QTimer(self)
        self._live_refresh_timer.setSingleShot(True)
        self._live_refresh_timer.setInterval(self.LIVE_REFRESH_DEBOUNCE_MS)
        self._live_refresh_timer.timeout.connect(self._refresh_selected_projection)
        self._event_filter_installed = False

        self.set_title_text(node.name)
        self._update_layer_info()

        # The node's primary icon is STACKS_ICON; the action on the right stays
        # the standard pen/edit button and is swapped out only while selecting.
        self.edit_button = TargetEditButton()
        self.edit_button.setToolTip("Select layers")
        self.edit_button.clicked.connect(self._toggle_editing)

        self.accept_button = self._create_action_button(CHECK_ICON, "Accept selected layers")
        self.accept_button.clicked.connect(self._accept_selection)

        self.cancel_button = self._create_action_button(CANCEL_ICON, "Cancel layer selection")
        self.cancel_button.clicked.connect(self._cancel_editing)

        # These child widgets are not in the layout until selection mode starts.
        # Explicitly hide them so Qt cannot show them at their default geometry
        # when the parent node widget becomes visible.
        self.accept_button.hide()
        self.cancel_button.hide()

        self.set_action_buttons([self.edit_button])

        self.layer_picker = LayerMultiSelectionPicker(window, document, self)
        self.layer_picker.cancelled.connect(self._reset_edit_controls)
        self.layer_picker.selection_accepted.connect(self._selection_accepted)

        # Krita does not expose a public document-pixels-changed signal.
        # Observe input on its actual canvas widgets, then capture once the
        # stroke or canvas command has settled.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._event_filter_installed = True

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
        if self.layer_ids or self.snapshot_revision:
            return

        state = LoadImageState(
            id=self.id,
            type=self.type,
            document_id=self.document_id,
            layer_ids=[],
            layer_names=[],
            snapshot_revision="",
        )
        self._apply_state(state)
        self.state_changed.emit(state)

    def cleanup(self) -> None:
        self._live_refresh_timer.stop()
        app = QApplication.instance()
        if self._event_filter_installed and app is not None:
            app.removeEventFilter(self)
        self._event_filter_installed = False

        if self.layer_picker.is_editing:
            self.layer_picker.cancel()

        # The node may remain alive until Qt processes deleteLater(). Remove
        # its action controls synchronously so none can outlive the node row.
        self.set_action_buttons([])
        action_buttons = self.findChildren(QToolButton)
        for button in action_buttons:
            qWarning(
                f"[Krita Docker] disposing Load Image action button "
                f"name={button.objectName()!r} text={button.text()!r} "
                f"visible={button.isVisible()} geometry={button.geometry().getRect()}"
            )
            button.hide()
            button.setEnabled(False)
            button.setParent(None)
            button.deleteLater()

        # Workers own only a detached QImage. Ignore their results after this
        # node is removed; the scratch document has already been closed.
        self._pending_state = None

    def apply(self, node_state: UiNodeState) -> None:
        self._apply_state(cast("LoadImageState", node_state))

    def _apply_state(self, state: LoadImageState) -> None:
        self.layer_ids = list(state.layer_ids)
        self.layer_names = list(state.layer_names)
        self.snapshot_revision = state.snapshot_revision
        self._update_layer_info()

    def _toggle_editing(self, _checked: bool) -> None:
        if self.layer_picker.is_editing:
            self._cancel_editing()
            return

        try:
            self.layer_picker.begin(self.layer_ids)
        except TargetSelectionUnavailableError as error:
            self.layer_info_text.setToolTip(str(error))
            LOGGER.warning("Could not start Krita layer selection: %s", error)
            return

        self.set_action_buttons([self.accept_button, self.cancel_button])

    def _accept_selection(self, *_args: object) -> None:
        try:
            self.layer_picker.accept()
        except (TargetSelectionUnavailableError, ValueError) as error:
            self.layer_info_text.setToolTip(str(error))
            LOGGER.warning("Could not accept Krita layer selection: %s", error)

    def _cancel_editing(self, *_args: object) -> None:
        self.layer_picker.cancel()
        self._reset_edit_controls()

    def _reset_edit_controls(self) -> None:
        self.set_action_buttons([self.edit_button])

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if self._is_canvas_input_event(watched, event):
            self._schedule_live_refresh()
        return super().eventFilter(watched, event)

    def _is_canvas_input_event(self, watched: QObject, event: QEvent) -> bool:
        if self.layer_picker.is_editing:
            return False
        active_view = self.window.activeView()
        if active_view is None or active_view.document() != self.document:
            return False
        if event.type() not in {
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.TabletRelease,
            QEvent.Type.TouchEnd,
            QEvent.Type.KeyRelease,
        }:
            return False

        current = watched
        while current is not None:
            if isinstance(current, QWidget):
                try:
                    class_name = current.metaObject().className()
                except RuntimeError:
                    return False
                if class_name in self.CANVAS_WIDGET_TYPES:
                    return True
                current = current.parentWidget()
            else:
                current = current.parent()
        return False

    def _schedule_live_refresh(self) -> None:
        if not self.layer_ids or self.layer_picker.is_editing:
            return
        self._live_refresh_timer.start()

    def _refresh_selected_projection(self) -> None:
        if not self.layer_ids or self.layer_picker.is_editing:
            return
        if self._pending_state is not None or self._composition_tasks:
            self._refresh_requested = True
            return

        selected_id_set = set(self.layer_ids)
        selected_nodes = [
            node
            for node in self.layer_picker._walk_nodes(self.document.rootNode())
            if str(node.uniqueId()) in selected_id_set
        ]
        if selected_nodes:
            self._capture_selected_nodes(selected_nodes)

    def _selection_accepted(self, selected_nodes: list[KritaNode]) -> None:
        self._reset_edit_controls()
        self._capture_selected_nodes(selected_nodes)

    def _capture_selected_nodes(self, selected_nodes: list[KritaNode]) -> None:
        try:
            projection = capture_selected_layers_projection(self.document, selected_nodes)
        except Exception as error:  # noqa: BLE001
            qWarning(
                "[Load Image node] capture failed "
                f"document={self.document.name()!r} node_id={self.id} "
                f"selected={[(str(node.uniqueId()), node.name(), node.type()) for node in selected_nodes]}\n"
                f"{traceback.format_exc()}"
            )
            self.layer_info_text.setToolTip(str(error))
            self.set_info_text("Layer capture failed")
            return

        layer_ids = [str(layer.uniqueId()) for layer in selected_nodes]
        layer_names = [layer.name() for layer in selected_nodes]
        revision = _projection_revision(projection)
        state = LoadImageState(
            id=self.id,
            type=self.type,
            document_id=self.document_id,
            layer_ids=layer_ids,
            layer_names=layer_names,
            snapshot_revision=revision,
        )
        if revision == self.snapshot_revision:
            # Selection metadata may have changed while the composed pixels
            # stayed identical. Synchronize the UI state without uploading or
            # changing the ComfyUI execution-cache token.
            self._apply_state(state)
            self.state_changed.emit(state)
            self.set_info_text(f"{len(layer_names)} selected layer(s) — unchanged")
            return

        self._pending_state = state
        self.set_info_text(f"Encoding {len(layer_names)} selected layer(s)…")

        task = _ProjectionExportTask(state, projection)
        task.signals.completed.connect(
            self._on_projection_export_completed,
            Qt.ConnectionType.QueuedConnection,
        )
        task.signals.failed.connect(
            self._on_projection_export_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        self._composition_tasks.add(task)
        self._composition_pool.start(task)

    def _on_projection_export_completed(
        self,
        task: _ProjectionExportTask,
        state: LoadImageState,
        image_data: bytes,
    ) -> None:
        self._composition_tasks.discard(task)
        if self._pending_state is None or self._pending_state.snapshot_revision != state.snapshot_revision:
            return

        self.set_info_text(f"Uploading {len(state.layer_names)} selected layer(s)…")
        self.snapshot_ready.emit(state, image_data)

    def _on_projection_export_failed(
        self,
        task: _ProjectionExportTask,
        state: LoadImageState,
        error: str,
    ) -> None:
        self._composition_tasks.discard(task)
        if self._pending_state is None or self._pending_state.snapshot_revision != state.snapshot_revision:
            return

        self._pending_state = None
        self.layer_info_text.setToolTip(error)
        self.set_info_text("Layer export failed")
        LOGGER.error("Could not export the selected Krita layer projection: %s", error)
        self._resume_requested_refresh()

    def snapshot_uploaded(self, state: LoadImageState) -> None:
        if self._pending_state is None or self._pending_state.snapshot_revision != state.snapshot_revision:
            return

        self._apply_state(state)
        self._pending_state = None
        self.state_changed.emit(state)
        self._resume_requested_refresh()

    def _resume_requested_refresh(self) -> None:
        if not self._refresh_requested:
            return
        self._refresh_requested = False
        self._live_refresh_timer.start(100)

    def snapshot_upload_failed(self, state: LoadImageState, error: str) -> None:
        if self._pending_state is None or self._pending_state.snapshot_revision != state.snapshot_revision:
            return

        self._pending_state = None
        self.layer_info_text.setToolTip(error)
        self.set_info_text("Upload failed — edit selection to retry")
        LOGGER.error("Could not upload the Krita layer snapshot: %s", error)
        self._resume_requested_refresh()

    def _update_layer_info(self) -> None:
        if not self.layer_ids:
            self.set_info_text("No layers selected")
        elif len(self.layer_names) == 1:
            self.set_info_text(f'Layer: "{self.layer_names[0]}"')
        else:
            self.set_info_text(f"{len(self.layer_names)} layers selected")
