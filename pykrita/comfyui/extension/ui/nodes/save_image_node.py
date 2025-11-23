from typing import ClassVar

from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout

from comfyui.extension.layer_manager import LayerManager, PersistentLayerNotifier
from comfyui.extension.models import FlatLayerToken, Node, PersistentLayer
from comfyui.extension.ui.icons import SAVE_ICON
from comfyui.extension.ui.micro.buttons import DirectionButton, VisibilityButton
from comfyui.extension.ui.micro.labels import NodeDescriptionLabel, NodeTitleLabel

from .comfyui_node import ComfyUiNode
from .miniature import Miniature


class SaveImageNode(ComfyUiNode):
    type: ClassVar[str | None] = "KritaSaveImage-15347"

    def __init__(self, node: Node, layer_manager: LayerManager) -> None:
        super().__init__(node, layer_manager)
        self.node_name = node.name
        self.layer_name: str = "Layer: "
        self.linked_layer: PersistentLayer | None = None
        self.layer_notifier: PersistentLayerNotifier | None = None

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 0, 0)

        self.miniature = Miniature(SAVE_ICON)
        self.main_layout.addWidget(self.miniature)

        self.middle_rack = QVBoxLayout()
        self.node_name_label = NodeTitleLabel(node.name)
        self.middle_rack.addWidget(self.node_name_label)

        self.layer_info_text = NodeDescriptionLabel(self.layer_name)
        self.middle_rack.addWidget(self.layer_info_text)

        self.main_layout.addLayout(self.middle_rack)
        self.main_layout.addStretch(1)

        self.action_buttons_container = QHBoxLayout()
        self.action_buttons_container.setSpacing(1)

        self.direction_button = DirectionButton()
        self.action_buttons_container.addWidget(self.direction_button)

        self.visibility_button = VisibilityButton()
        self.visibility_button.changed_to_visible.connect(self._show_linked_layer)
        self.visibility_button.changed_to_hidden.connect(self._hide_linked_layer)
        self.action_buttons_container.addWidget(self.visibility_button)

        self.main_layout.addLayout(self.action_buttons_container)

        self._update_layer_name("Generator Position")
        self._create_layer()
        assert self.linked_layer is not None  # noqa: S101

        self.layer_notifier = self.layer_manager.notifier(self.linked_layer)
        self.layer_notifier.user_unrendered.connect(self._hide_linked_layer)
        self.layer_notifier.name_changed.connect(self._update_layer_name)

    def cleanup(self) -> None:
        if self.linked_layer is None:
            return

        self.layer_manager.delete(self.linked_layer)

    def _show_linked_layer(self) -> None:
        assert self.linked_layer is not None  # noqa: S101
        self.layer_manager.show(self.linked_layer)

    def _hide_linked_layer(self) -> None:
        assert self.linked_layer is not None  # noqa: S101
        self.layer_manager.hide(self.linked_layer)

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
