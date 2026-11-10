import logging
import uuid
from typing import ClassVar, cast

from krita import DockWidget, Document, Node as KritaNode, Window
from PyQt5.QtCore import Qt, pyqtBoundSignal, pyqtSignal
from PyQt5.QtWidgets import QToolButton

from comfyui.extension.layer_tree.multi_selection_picker import LayerMultiSelectionPicker
from comfyui.extension.layer_tree.selection_exporter import export_selected_layers
from comfyui.extension.layer_tree.target_picker import TargetSelectionUnavailableError
from comfyui.extension.models import LoadImageState, Node, UiNodeState
from comfyui.extension.ui.icons import LAYERS_ICON
from comfyui.extension.ui.micro.buttons import TargetEditButton

from .comfyui_node import ComfyUiNode

LOGGER = logging.getLogger(__name__)


class LoadImageNode(ComfyUiNode):
    type: ClassVar[str] = "KritaLoadImage-15348"
    snapshot_ready = cast("pyqtBoundSignal", pyqtSignal(object, bytes))

    def __init__(self, docker: DockWidget, node: Node, window: Window, document: Document, document_id: str) -> None:
        super().__init__(docker, node, LAYERS_ICON, document_id)
        self.setObjectName("LoadImageNode")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, on=True)
        self.window = window
        self.document = document
        self.layer_ids: list[str] = []
        self.layer_names: list[str] = []
        self.snapshot_revision = ""
        self._pending_state: LoadImageState | None = None
        self._applying_state = False

        self.set_title_text(node.name)
        self._update_layer_info()

        self.edit_button = TargetEditButton()
        self.edit_button.clicked.connect(self._toggle_editing)

        self.accept_button = QToolButton()
        self.accept_button.setText("Accept")
        self.accept_button.setToolTip("Accept the selected Krita layers")
        self.accept_button.setAutoRaise(True)
        self.accept_button.clicked.connect(self._accept_selection)

        self.cancel_button = QToolButton()
        self.cancel_button.setText("Cancel")
        self.cancel_button.setToolTip("Cancel layer selection")
        self.cancel_button.setAutoRaise(True)
        self.cancel_button.clicked.connect(self._cancel_editing)

        self.set_action_buttons([self.edit_button])

        self.layer_picker = LayerMultiSelectionPicker(window, document, self)
        self.layer_picker.cancelled.connect(self._reset_edit_controls)
        self.layer_picker.selection_accepted.connect(self._selection_accepted)

    def initialize_state(self) -> None:
        if self._pending_state is not None:
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
        if self.layer_picker.is_editing:
            self.layer_picker.cancel()

    def apply(self, node_state: UiNodeState) -> None:
        self._apply_state(cast("LoadImageState", node_state))

    def _apply_state(self, state: LoadImageState) -> None:
        self._applying_state = True
        try:
            self.layer_ids = list(state.layer_ids)
            self.layer_names = list(state.layer_names)
            self.snapshot_revision = state.snapshot_revision
            self._update_layer_info()
        finally:
            self._applying_state = False

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

    def _accept_selection(self, _checked: bool = False) -> None:
        try:
            self.layer_picker.accept()
        except (TargetSelectionUnavailableError, ValueError) as error:
            self.layer_info_text.setToolTip(str(error))
            LOGGER.warning("Could not accept Krita layer selection: %s", error)

    def _cancel_editing(self, _checked: bool = False) -> None:
        self.layer_picker.cancel()
        self._reset_edit_controls()

    def _reset_edit_controls(self) -> None:
        self.set_action_buttons([self.edit_button])

    def _selection_accepted(self, selected_nodes: list[KritaNode]) -> None:
        self._reset_edit_controls()
        layer_ids = [str(layer.uniqueId()) for layer in selected_nodes]
        layer_names = [layer.name() for layer in selected_nodes]

        try:
            image_data = export_selected_layers(self.document, layer_ids)
        except Exception as error:  # noqa: BLE001
            LOGGER.exception("Could not export the selected Krita layers")
            self.layer_info_text.setToolTip(str(error))
            self.set_info_text("Layer export failed")
            return

        state = LoadImageState(
            id=self.id,
            type=self.type,
            document_id=self.document_id,
            layer_ids=layer_ids,
            layer_names=layer_names,
            snapshot_revision=uuid.uuid4().hex,
        )
        self._pending_state = state
        self.set_info_text(f"Uploading {len(layer_names)} selected layer(s)…")
        self.snapshot_ready.emit(state, image_data)

    def snapshot_uploaded(self, state: LoadImageState) -> None:
        if self._pending_state is None or self._pending_state.snapshot_revision != state.snapshot_revision:
            return

        self._apply_state(state)
        self._pending_state = None
        self._update_layer_info()
        self.state_changed.emit(state)

    def snapshot_upload_failed(self, state: LoadImageState, error: str) -> None:
        if self._pending_state is None or self._pending_state.snapshot_revision != state.snapshot_revision:
            return

        self._pending_state = None
        self.layer_info_text.setToolTip(error)
        self.set_info_text("Upload failed — edit selection to retry")
        LOGGER.error("Could not upload the Krita layer snapshot: %s", error)

    def _update_layer_info(self) -> None:
        if not self.layer_ids:
            self.set_info_text("No layers selected")
        elif len(self.layer_names) == 1:
            self.set_info_text(f'Layer: "{self.layer_names[0]}"')
        else:
            self.set_info_text(f"{len(self.layer_names)} layers selected")
