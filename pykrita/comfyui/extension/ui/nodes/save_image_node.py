from typing import ClassVar

from krita import DockWidget

from comfyui.extension.layer_manager import LayerManager, PersistentLayerNotifier
from comfyui.extension.models import FlatLayerToken, Node, PersistentLayer
from comfyui.extension.ui.icons import SAVE_ICON
from comfyui.extension.ui.micro.buttons import DirectionButton, VisibilityButton

from .comfyui_node import ComfyUiNode


class SaveImageNode(ComfyUiNode):
    type: ClassVar[str | None] = "KritaSaveImage-15347"

    def __init__(self, docker: DockWidget, node: Node, layer_manager: LayerManager) -> None:
        super().__init__(docker, node, SAVE_ICON)
        self.layer_manager = layer_manager
        self.node_name = node.name
        self.layer_name: str = "Layer: "
        self.linked_layer: PersistentLayer | None = None
        self.layer_notifier: PersistentLayerNotifier | None = None

        self.set_title_text(node.name)
        self.set_info_text(self.layer_name)

        self.direction_button = DirectionButton()
        self.visibility_button = VisibilityButton()
        self.visibility_button.changed_to_visible.connect(self._show_linked_layer)
        self.visibility_button.changed_to_hidden.connect(self._hide_linked_layer)

        self.set_action_buttons(
            [
                self.direction_button,
                self.visibility_button,
            ],
        )

        self._update_layer_name("Generator Position")
        self._create_layer()
        assert self.linked_layer is not None  # noqa: S101

        notifier = self.layer_manager.notifier(self.linked_layer)
        notifier.user_unrendered.connect(self._hide_linked_layer)
        notifier.user_rendered.connect(self._show_linked_layer)
        notifier.name_changed.connect(self._update_layer_name)

    def cleanup(self) -> None:
        if self.linked_layer is None:
            return

        self.layer_manager.delete(self.linked_layer)

    def _show_linked_layer(self) -> None:
        assert self.linked_layer is not None  # noqa: S101
        self.layer_manager.show(self.linked_layer)
        self.visibility_button.set_visibility_on_visual()

    def _hide_linked_layer(self) -> None:
        assert self.linked_layer is not None  # noqa: S101
        self.layer_manager.hide(self.linked_layer)
        self.visibility_button.set_visibility_off_visual()

    def _update_layer_name(self, name: str) -> None:
        self.layer_name = name
        self.layer_info_text.setText(f'Layer: "{name}"')

    def _create_layer(self) -> None:
        if self.linked_layer is not None and self.layer_manager.exists(self.linked_layer):
            return

        name = self._generate_layer_name()
        path = self._generate_layer_path()
        self.linked_layer = self.layer_manager.create(name, path)

    def _generate_layer_name(self) -> str:
        return self.layer_name

    def _generate_layer_path(self) -> list[FlatLayerToken] | None:
        return None
