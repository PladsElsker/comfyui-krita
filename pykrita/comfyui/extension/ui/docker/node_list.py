from krita import Document, Window
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from comfyui.extension.models import Node, NodeDirection, UiNodeState
from comfyui.extension.ui.nodes.comfyui_node import ComfyUiNode
from comfyui.extension.ui.nodes.node_factory import NodeFactory

NodeKey = tuple[int, str, str | None]


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
        self.previous_node_states: dict[NodeKey, UiNodeState] = {}

    def update_from_comyui(self, nodes: list[Node], window: Window, document: Document, document_id: str) -> None:
        comfyui_node_mapping = {self._get_node_key(node, document_id): node for node in nodes}
        current_node_mapping = {self._get_node_key(node_widget, document_id): node_widget for node_widget in self.node_widgets}

        incoming_keys = comfyui_node_mapping.keys()
        existing_keys = current_node_mapping.keys()

        to_delete_keys = existing_keys - incoming_keys
        to_create_keys = incoming_keys - existing_keys

        self._clear_main_layout()

        for to_delete_key in to_delete_keys:
            widget: ComfyUiNode = current_node_mapping[to_delete_key]

            if isinstance(widget, ComfyUiNode):
                widget.cleanup()
                widget.deleteLater()
                self.node_widgets.remove(widget)

        for to_create_key in to_create_keys:
            to_create = comfyui_node_mapping[to_create_key]
            node_widget = NodeFactory.create(self, to_create, window, document, document_id)

            if to_create_key in self.previous_node_states:
                previous_node_state = self.previous_node_states[to_create_key]
                node_widget.apply(previous_node_state)

            node_widget.state_changed.connect(self._register_node_state)
            self.node_widgets.append(node_widget)

        self._fill_main_layout()

    def _clear_main_layout(self) -> None:
        while self.main_layout.count() > 0:
            item = self.main_layout.takeAt(0)

            if item is not None:
                layout_widget: QWidget = item.widget()

                if layout_widget is not None and not isinstance(layout_widget, ComfyUiNode):
                    layout_widget.deleteLater()

    def _fill_main_layout(self) -> None:
        input_mode: NodeDirection = "input"
        output_mode: NodeDirection = "output"

        input_node_widgets = [node_widget for node_widget in self.node_widgets if node_widget.direction == input_mode]
        output_node_widgets = [node_widget for node_widget in self.node_widgets if node_widget.direction == output_mode]

        self._add_node_group(input_node_widgets, "TO COMFYUI (INPUTS)")
        self._add_node_group(output_node_widgets, "FROM COMFYUI (OUTPUTS)")

        self.main_layout.addStretch(1)

    def _add_node_group(self, nodes: list[ComfyUiNode], title: str) -> None:
        if len(nodes) > 0:
            self.main_layout.addWidget(GroupTitle(title))

        for i, node_widget in enumerate(nodes):
            self.main_layout.addWidget(node_widget)
            if i < len(nodes) - 1:
                self._add_separator()

    def _add_separator(self) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: rgba(0, 0, 0, 20); border: none;")
        self.main_layout.addWidget(line)

    def _register_node_state(self, state: UiNodeState) -> None:
        self.previous_node_states[self._get_node_key(state)] = state

    def _get_node_key(self, node: Node | ComfyUiNode | UiNodeState, document_id: str | None = None) -> NodeKey:
        if document_id is None and not hasattr(node, "document_id"):
            message = "Unable to create a valid node key without a document id"
            raise ValueError(message)

        return (node.id, node.type, document_id if document_id is not None else getattr(node, "document_id", None))


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
