from krita import Document, Window
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from comfyui.extension.models import Node, NodeDirection, UiNodeState
from comfyui.extension.ui.nodes.comfyui_node import ComfyUiNode
from comfyui.extension.ui.nodes.node_factory import NodeFactory


class NodeListWidget(QScrollArea):
    def __init__(self) -> None:
        super().__init__()

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(4, 0, 4, 0)

        self.container = QWidget()
        self.container.setLayout(self.main_layout)

        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setFrameShadow(QScrollArea.Shadow.Plain)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setWidget(self.container)

        self.node_widgets: list[ComfyUiNode] = []
        self.prevous_node_states: dict[tuple[int, str, str], UiNodeState] = {}

    def update_from_comyui(self, nodes: list[Node], window: Window, document: Document, document_id: str) -> None:
        def _nid(node: Node) -> tuple:
            return (node.id, node.type, document_id)

        comfyui_node_mapping = {_nid(node): node for node in nodes}
        current_node_mapping = {_nid(node_widget): node_widget for node_widget in self.node_widgets}

        nodes_to_delete = [
            current_node_mapping[_nid(node_widget)] for node_widget in self.node_widgets if _nid(node_widget) not in comfyui_node_mapping
        ]
        nodes_to_create = [node for node in nodes if _nid(node) not in current_node_mapping]

        while self.main_layout.count() > 0:
            item = self.main_layout.takeAt(0)

            if item is not None:
                layout_widget: QWidget = item.widget()

                if layout_widget is not None and not isinstance(layout_widget, ComfyUiNode):
                    layout_widget.deleteLater()

        for to_delete in nodes_to_delete:
            node_id = _nid(to_delete)
            widget: ComfyUiNode = current_node_mapping[node_id]

            if isinstance(widget, ComfyUiNode):
                widget.cleanup()
                widget.deleteLater()
                self.node_widgets.remove(widget)

        for to_create in nodes_to_create:
            node_widget = NodeFactory.create(self, to_create, window, document, document_id)
            node_id = _nid(to_create)

            if node_id in self.prevous_node_states:
                previous_node_state = self.prevous_node_states[node_id]
                node_widget.apply(previous_node_state)

            node_widget.state_changed.connect(self._register_node_state)
            self.node_widgets.append(node_widget)

        self._refresh_ui()

    def _refresh_ui(self) -> None:
        input_mode: NodeDirection = "input"
        output_mode: NodeDirection = "output"

        input_node_widgets = [node_widget for node_widget in self.node_widgets if node_widget.direction == input_mode]
        output_node_widgets = [node_widget for node_widget in self.node_widgets if node_widget.direction == output_mode]

        if len(input_node_widgets) > 0:
            self.main_layout.addWidget(GroupTitle("TO COMFYUI (INPUTS)"))

        for i, node_widget in enumerate(input_node_widgets):
            self.main_layout.addWidget(node_widget)
            if i < len(input_node_widgets) - 1:
                self._add_separator()

        if len(output_node_widgets) > 0:
            self.main_layout.addWidget(GroupTitle("FROM COMFYUI (OUTPUTS)"))

        for i, node_widget in enumerate(output_node_widgets):
            self.main_layout.addWidget(node_widget)
            if i < len(output_node_widgets) - 1:
                self._add_separator()

        self.main_layout.addStretch(1)

    def _add_separator(self) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: rgba(0, 0, 0, 20); border: none;")
        self.main_layout.addWidget(line)

    def _register_node_state(self, state: UiNodeState) -> None:
        self.prevous_node_states[(state.id, state.type, state.document_id)] = state


class GroupTitle(QLabel):
    def __init__(self, group_name: str) -> None:
        super().__init__(group_name)
        self.setContentsMargins(0, 4, 0, 0)

        font = self.font()
        font.setBold(True)
        self.setFont(font)
        palette = self.palette()
        disabled_color = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText)
        self.setStyleSheet(f"color: {disabled_color.name()};")
