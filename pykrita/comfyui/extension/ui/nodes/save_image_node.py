import logging
from typing import ClassVar, Literal, cast

from krita import DockWidget, Document, Node as KritaNode, Window
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QLabel

from comfyui.extension.layer_tree.target_picker import LayerTargetPicker, TargetSelectionUnavailableError
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

        self.set_title_text(node.name)
        self._update_layer_name(self.layer_name, is_set=False)

        self._configure_target_edit_style()

        self.direction_button = DirectionButton()
        self.direction_button.changed_to_above.connect(self._set_above_direction)
        self.direction_button.changed_to_below.connect(self._set_below_direction)

        self.target_button = TargetEditButton()
        self.target_button.clicked.connect(self._toggle_target_editing)

        self.set_action_buttons([self.direction_button, self.target_button])

        self.target_picker = LayerTargetPicker(window, document, self)
        self.target_picker.target_selected.connect(self._set_target)
        self.target_picker.target_removed.connect(self._clear_deleted_target)
        self.target_picker.target_renamed.connect(self._update_target_name)
        self.target_picker.cancelled.connect(self._reset_target_button)

    def initialize_state(self) -> None:
        if self.layer_path:
            return

        self.layer_path = [FlatLayerToken(quuid=None, type="target")]
        self._update_layer_name("Not set", is_set=False)
        self._consolidate_state()

    def cleanup(self) -> None:
        if self.target_picker.is_editing:
            self.target_picker.cancel()

    def apply(self, node_state: UiNodeState) -> None:
        state = cast("SaveImageState", node_state)
        self._applying_state = True
        try:
            self.layer_path = list(state.path)
            self.layer_name = state.layer_name
            marker = next((token for token in self.layer_path if token.type == "target"), None)
            target_id = str(marker.quuid) if marker is not None and marker.quuid is not None else None
            self._update_layer_name(self.layer_name, is_set=target_id is not None)
            self.target_picker.watch_target(target_id, state.layer_name if target_id is not None else None)

            should_insert_below = state.insert_direction == "below"
            if self.direction_button.is_inserting_below() != should_insert_below:
                self.direction_button.toggle_state()
        finally:
            self._applying_state = False

    def _toggle_target_editing(self, _checked: bool) -> None:
        if self.target_picker.is_editing:
            self.target_picker.cancel()
            return

        target = LayerUtils.find_target_node(self.document, self.layer_path)
        try:
            self.target_picker.begin(target)
        except TargetSelectionUnavailableError as error:
            self._set_target_editing_feedback(editing=False)
            self.layer_info_text.setToolTip(str(error))
            LOGGER.warning("Could not start Krita output target editing: %s", error)
            return

        self._set_target_editing_feedback(editing=True)

    def _set_target(self, target: KritaNode) -> None:
        direction = "below" if self.direction_button.is_inserting_below() else "above"
        try:
            path = LayerUtils.capture_target(self.document, target, direction)
        finally:
            self._set_target_editing_feedback(editing=False)

        self.layer_path = path
        self.target_picker.watch_target(str(target.uniqueId()), target.name())
        self._update_layer_name(target.name())
        self._consolidate_state()

    def _clear_deleted_target(self, target_id: str) -> None:
        marker = next((token for token in self.layer_path if token.type == "target"), None)
        if marker is None or marker.quuid is None or str(marker.quuid) != target_id:
            return

        # Persist a null target for future prompts. In-flight prompts keep
        # their own path snapshot and resolve deletion during result insertion.
        self.layer_path = [FlatLayerToken(quuid=None, type="target")]
        self._update_layer_name("Not set", is_set=False)
        self._consolidate_state()

    def _update_target_name(self, name: str) -> None:
        self._update_layer_name(name)
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

    def _reset_target_button(self) -> None:
        self._set_target_editing_feedback(editing=False)

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
