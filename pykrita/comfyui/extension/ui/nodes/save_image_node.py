import logging
from typing import ClassVar, Literal, cast

from krita import DockWidget, Document, Node as KritaNode, Window

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
        self.window = window
        self.document = document
        self.layer_name = "Not set"
        self.layer_path: list[FlatLayerToken] = []
        self._applying_state = False

        self.set_title_text(node.name)
        self._update_layer_name(self.layer_name)

        self.direction_button = DirectionButton()
        self.direction_button.changed_to_above.connect(self._set_above_direction)
        self.direction_button.changed_to_below.connect(self._set_below_direction)

        self.target_button = TargetEditButton()
        self.target_button.clicked.connect(self._toggle_target_editing)

        self.set_action_buttons([self.direction_button, self.target_button])

        self.target_picker = LayerTargetPicker(window, document, self)
        self.target_picker.target_selected.connect(self._set_target)
        self.target_picker.cancelled.connect(self._reset_target_button)

    def cleanup(self) -> None:
        if self.target_picker.is_editing:
            self.target_picker.cancel()

    def apply(self, node_state: UiNodeState) -> None:
        state = cast("SaveImageState", node_state)
        self._applying_state = True
        try:
            self.layer_path = list(state.path)
            self.layer_name = state.layer_name
            self._update_layer_name(self.layer_name)

            should_insert_below = state.insert_direction == "below"
            if self.direction_button.is_inserting_below() != should_insert_below:
                self.direction_button.toggle_state()
        finally:
            self._applying_state = False

    def _toggle_target_editing(self, _checked: bool) -> None:
        target = LayerUtils.find_target_node(self.document, self.layer_path)
        try:
            self.target_picker.begin(target)
        except TargetSelectionUnavailableError as error:
            self.target_button.set_editing(False)
            self.layer_info_text.setToolTip(str(error))
            LOGGER.warning("Could not start Krita output target editing: %s", error)
            return

        self.target_button.set_editing(True)

    def _set_target(self, target: KritaNode) -> None:
        direction = "below" if self.direction_button.is_inserting_below() else "above"
        self.layer_path = LayerUtils.capture_target(self.document, target, direction)
        self._update_layer_name(target.name())
        self.target_button.set_editing(False)
        self._consolidate_state()

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
        self.target_button.set_editing(False)

    def _update_layer_name(self, name: str) -> None:
        self.layer_name = name
        self.set_info_text(f'Layer: "{name}"')

    def insert_image_node(self, image_node: KritaNode, path: list[FlatLayerToken]) -> None:
        """Insert an output image using the path registered with its ComfyUI prompt."""
        relative_path = LayerUtils.rebase_path(self.document, path)
        if relative_path is None:
            message = "The rebased output insertion parent no longer exists"
            raise ValueError(message)

        relative_path.parent.addChildNode(image_node, relative_path.sibling)

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
