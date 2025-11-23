from typing import ClassVar

from PyQt5.QtWidgets import QWidget

from comfyui.extension.layer_manager import LayerManager
from comfyui.extension.models import Node, NodeDirection


class ComfyUiNode(QWidget):
    type: ClassVar[str | None] = None
    direction: NodeDirection

    def __init__(self, node: Node, layer_manager: LayerManager) -> None:
        super().__init__()
        self.direction = node.direction
        self.layer_manager = layer_manager

    def cleanup(self) -> None: ...
