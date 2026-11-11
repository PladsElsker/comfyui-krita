import logging
from typing import ClassVar, Literal, cast

from krita import DockWidget, Document, Node as KritaNode, Window
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QLabel

from comfyui.extension.layer_tree.document_change_tracker import document_change_tracker
from comfyui.extension.layer_tree.selection_modal import select_layers
from comfyui.extension.layer_tree.utils import LayerUtils
from comfyui.extension.models import FlatLayerToken, Node, SaveImageState, UiNodeState
from comfyui.extension.ui.icons import SAVE_ICON
from comfyui.extension.ui.micro.buttons import DirectionButton, TargetEditButton

from .comfyui_node import ComfyUiNode

LOGGER = logging.getLogger(__name__)


class SaveImageNode(ComfyUiNode):
    type: ClassVar[str] = "KritaSaveImage-15347"

    def __init__(self, docker: DockWidget, node: Node, window: Window, document: Document, document_id: str) -> None:
        super().__init__(docker, node, SAVE_ICON, document_id)
        self.setObjectName("SaveImageNode")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, on=True)
        self.window = window
        self.document = document
        self.layer_name = "Not set"
        self.layer_path: list[FlatLayerToken] = []
        self._applying_state = False
        self._modal_active = False
        self._target_node_id: str | None = None
        self._change_tracker = document_change_tracker()

        self.set_title_text(node.name)
        self._update_layer_name(self.layer_name, is_set=False)

        self._configure_target_edit_style()

        self.direction_button = DirectionButton()
        self.direction_button.changed_to_above.connect(self._set_above_direction)
        self.direction_button.changed_to_below.connect(self._set_below_direction)

        self.target_button = TargetEditButton()
        self.target_button.clicked.connect(self._toggle_target_editing)

        self.set_action_buttons([self.direction_button, self.target_button])

        self._change_tracker.watch(document, window, self, self._on_document_changed)

    def initialize_state(self) -> None:
        if self.layer_path:
            return

        self.layer_path = [FlatLayerToken(quuid=None, type="target")]
        self._update_layer_name("Not set", is_set=False)
        self._consolidate_state()

    def cleanup(self) -> None:
        self._change_tracker.unwatch(self.document, self)
        self._set_target_editing_feedback(editing=False)

    def apply(self, node_state: UiNodeState) -> None:
        state = cast("SaveImageState", node_state)
        self._applying_state = True
        try:
            self.layer_path = list(state.path)
            self.layer_name = state.layer_name
            marker = next((token for token in self.layer_path if token.type == "target"), None)
            target_id = str(marker.quuid) if marker is not None and marker.quuid is not None else None
            self._target_node_id = target_id
            self._update_layer_name(self.layer_name, is_set=target_id is not None)

            should_insert_below = state.insert_direction == "below"
            if self.direction_button.is_inserting_below() != should_insert_below:
                self.direction_button.toggle_state()
        finally:
            self._applying_state = False

    def _toggle_target_editing(self, _checked: bool) -> None:
        if self._modal_active:
            return

        self._modal_active = True
        self._set_target_editing_feedback(editing=True)
        try:
            selected_nodes = select_layers(
                self.document,
                mode="single",
                selected_ids=[self._target_node_id] if self._target_node_id else None,
                parent=self,
            )
            if selected_nodes:
                self._set_target(selected_nodes[0])
        finally:
            self._modal_active = False
            self._set_target_editing_feedback(editing=False)

    def _set_target(self, target: KritaNode) -> None:
        direction = "below" if self.direction_button.is_inserting_below() else "above"
        path = LayerUtils.capture_target(self.document, target, direction)
        self._target_node_id = str(target.uniqueId())
        self.layer_path = path
        self._update_layer_name(target.name())
        self._consolidate_state()

    def _on_document_changed(self) -> None:
        if self._modal_active or self._target_node_id is None:
            return

        target = LayerUtils.find_target_node(self.document, self.layer_path)
        if target is None:
            self._clear_deleted_target(self._target_node_id)
            return

        direction = "below" if self.direction_button.is_inserting_below() else "above"
        try:
            path = LayerUtils.capture_target(self.document, target, direction)
        except (RuntimeError, ValueError):
            LOGGER.exception("Could not refresh the Krita output target position")
            return

        target_name = target.name()
        if path == self.layer_path and target_name == self.layer_name:
            return

        self.layer_path = path
        self._update_layer_name(target_name)
        self._consolidate_state()

    def _clear_deleted_target(self, target_id: str) -> None:
        if self._target_node_id != target_id:
            return

        # In-flight prompts retain their own path snapshot. Future prompts
        # insert at the document root until the user chooses another target.
        self._target_node_id = None
        self.layer_path = [FlatLayerToken(quuid=None, type="target")]
        self._update_layer_name("Not set", is_set=False)
        self._consolidate_state()

    def _configure_target_edit_style(self) -> None:
        highlight = self.palette().color(QPalette.ColorRole.Highlight)
        background = QColor(highlight)
        background.setAlpha(24)
        self.setStyleSheet(
            'QWidget#SaveImageNode[targetEditing="true"] {'
            f"border: 1px solid {highlight.name()};"
            "border-radius: 5px;"
            f"background-color: rgba({background.red()}, {background.green()}, {background.blue()}, {background.alpha()});"
            "}"
        )
        self.setProperty("targetEditing", False)  # noqa: FBT003

    def _set_target_editing_feedback(self, *, editing: bool) -> None:
        self.target_button.set_editing(editing)
        self.setProperty("targetEditing", editing)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _set_above_direction(self) -> None:
        self._set_direction("above")

    def _set_below_direction(self) -> None:
        self._set_direction("below")

    def _set_direction(self, direction: Literal["above", "below"]) -> None:
        if self._applying_state:
            return

        if self.layer_path:
            self.layer_path = LayerUtils.set_target_direction(self.layer_path, direction)

        self._consolidate_state()

    def _update_layer_name(self, name: str, *, is_set: bool = True) -> None:
        self.layer_name = name
        if is_set:
            disabled_color = self.layer_info_text.palette().color(QPalette.ColorGroup.Normal, QPalette.ColorRole.Highlight)
            self.layer_info_text.setStyleSheet(f"color: {disabled_color.name()};")
            self.set_info_text(f'Layer: "{name}"')
        else:
            highlight = self.palette().color(QPalette.ColorRole.BrightText)
            self.layer_info_text.setStyleSheet(f"color: {highlight.name()}; font-weight: bold;")
            self.set_info_text("Layer: Not set")

    def insert_image_node(self, image_node: KritaNode, path: list[FlatLayerToken]) -> None:
        """Insert an output image using the path registered with its ComfyUI prompt."""
        LayerUtils.insert_node(self.document, image_node, path)

    def _consolidate_state(self) -> None:
        if not self.layer_path:
            return

        state = SaveImageState(
            id=self.id,
            type=self.type,
            document_id=self.document_id,
            insert_direction="below" if self.direction_button.is_inserting_below() else "above",
            path=self.layer_path,
            layer_name=self.layer_name,
        )
        self.state_changed.emit(state)
