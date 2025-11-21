from typing import ClassVar

from PyQt5.QtWidgets import QWidget

from ....layers_manager import PersistentLayerManager
from ....models import Node, NodeDirection


class ComfyUiNode(QWidget):
    type: ClassVar[str | None] = None
    direction: NodeDirection

    def __init__(self, node: Node, layers_manager: PersistentLayerManager) -> None:
        super().__init__()
        self.direction = node.direction
        self.layers_manager = layers_manager

    def cleanup(self) -> None: ...
