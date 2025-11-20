from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ...models import Node
from .nodes.node_factory import NodeFactory

if TYPE_CHECKING:
    from .nodes.comfyui_node import ComfyUiNode


class NodeListWidget(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setFrameShadow(QScrollArea.Shadow.Plain)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWidgetResizable(True)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(4, 4, 4, 4)

        self.container = QWidget()
        self.container.setLayout(self.main_layout)

        self.setWidget(self.container)

        self.node_widgets: list[ComfyUiNode] = []

    def rebuild(self, nodes: list[Node]) -> None:
        while self.main_layout.count() > 0:
            item = self.main_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        self.node_widgets.clear()

        for node in nodes:
            node_widget = NodeFactory.create(node)
            self.main_layout.insertWidget(self.main_layout.count() - 1, node_widget)
            self.node_widgets.append(node_widget)

        self.main_layout.addStretch(1)
