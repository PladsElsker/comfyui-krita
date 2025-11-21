from PyQt5.QtCore import qDebug
from PyQt5.QtWidgets import QHBoxLayout, QLabel

from ....layers_manager import PersistentLayerManager
from ....models import Node
from .comfyui_node import ComfyUiNode

COMBO_ABOVE_TEXT = "Insert Layers Above"
COMBO_BELOW_TEXT = "Insert Layers Below"
ARROW_UP = "↑"
ARROW_DOWN = "↓"


class TestNode(ComfyUiNode):
    type: str | None = "KritaSaveImage-15347"

    def __init__(self, node: Node, layers_manager: PersistentLayerManager) -> None:
        super().__init__(node, layers_manager)
        self.node_name = node.name
        self.linked_layer = None

        self.main_layout = QHBoxLayout()
        self.main_layout.addWidget(QLabel("Test Node"))
        self.setLayout(self.main_layout)

        qDebug("1")
        test_1 = layers_manager.create("Test 1")
        test_2 = layers_manager.create("Test 2")
        test_3 = layers_manager.create("Test 3")
        layers_manager.delete(test_1)
        layers_manager.delete(test_2)
        layers_manager.delete(test_3)
        qDebug("2")

    def cleanup(self) -> None:
        pass
