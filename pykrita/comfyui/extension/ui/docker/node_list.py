from krita import Document
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ...layers_manager import PersistentLayerManager
from ...models import Node, NodeDirection
from .nodes.comfyui_node import ComfyUiNode
from .nodes.node_factory import NodeFactory


class NodeListWidget(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setFrameShadow(QScrollArea.Shadow.Plain)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWidgetResizable(True)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(4, 0, 4, 0)

        self.container = QWidget()
        self.container.setLayout(self.main_layout)

        self.setWidget(self.container)

        self.node_widgets: list[ComfyUiNode] = []

    def rebuild(self, nodes: list[Node], document: Document) -> None:
        while self.main_layout.count() > 0:
            item = self.main_layout.takeAt(0)

            if item is not None:
                widget = item.widget()
                if widget is not None:
                    if isinstance(widget, ComfyUiNode):
                        widget.cleanup()

                    widget.deleteLater()

        self.node_widgets.clear()

        for node in nodes:
            node_widget = NodeFactory.create(node, PersistentLayerManager.get_by_document(document))
            self.node_widgets.append(node_widget)

        input_mode: NodeDirection = "input"
        output_mode: NodeDirection = "output"

        input_node_widgets = [node_widget for node_widget in self.node_widgets if node_widget.direction == input_mode]
        output_node_widgets = [node_widget for node_widget in self.node_widgets if node_widget.direction == output_mode]

        if len(input_node_widgets) > 0:
            self.main_layout.addWidget(GroupTitle("TO COMFYUI (INPUTS)"))

        for node_widget in input_node_widgets:
            self.main_layout.addWidget(node_widget)

        if len(output_node_widgets) > 0:
            self.main_layout.addWidget(GroupTitle("FROM COMFYUI (OUTPUTS)"))

        for node_widget in output_node_widgets:
            self.main_layout.addWidget(node_widget)

        self.main_layout.addStretch(1)


class GroupTitle(QLabel):
    def __init__(self, group_name: str) -> None:
        super().__init__(group_name)
        self.setContentsMargins(0, 4, 0, 0)

        font = self.font()
        font.setBold(True)
        self.setFont(font)
        self.setStyleSheet("color: #909090;")
