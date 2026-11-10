from typing import ClassVar, cast

from krita import DockWidget
from PyQt5.QtCore import pyqtBoundSignal, pyqtSignal
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QHBoxLayout, QToolButton, QVBoxLayout, QWidget

from comfyui.extension.models import Node, NodeDirection, UiNodeState
from comfyui.extension.ui.micro.labels import NodeDescriptionLabel, NodeTitleLabel

from .miniature import Miniature


class ComfyUiNode(QWidget):
    state_changed = cast("pyqtBoundSignal", pyqtSignal(object))
    type: ClassVar[str]
    direction: NodeDirection
    id: int

    def __init__(self, docker: DockWidget, node: Node, default_icon: QSvgRenderer, document_id: str) -> None:
        super().__init__()
        self.direction = node.direction
        self.miniature = Miniature(default_icon)
        self.id = node.id
        self.name = node.name
        self.document_id = document_id

        self.node_name_label = NodeTitleLabel()
        self.layer_info_text = NodeDescriptionLabel()

        self.middle_rack = QVBoxLayout()
        self.middle_rack.addWidget(self.node_name_label)
        self.middle_rack.addWidget(self.layer_info_text)

        self.action_buttons_container = QHBoxLayout()
        self.action_buttons_container.setSpacing(1)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 0, 0)
        self.main_layout.addWidget(self.miniature)
        self.main_layout.addLayout(self.middle_rack)
        self.main_layout.addStretch(1)
        self.main_layout.addLayout(self.action_buttons_container)

        def elided_width_fun() -> int:
            self.main_layout.activate()
            w0 = self.main_layout.itemAt(0).widget().width()  # type: ignore
            w1 = self.main_layout.itemAt(1).layout().geometry().width()  # type: ignore
            w3 = self.main_layout.itemAt(3).layout().geometry().width()  # type: ignore
            wt = docker.width()
            w2 = wt - (w0 + w1 + w3)
            return w1 + w2 - 24

        self.node_name_label.set_elided_width_producer(elided_width_fun)
        self.layer_info_text.set_elided_width_producer(elided_width_fun)

    def set_title_text(self, text: str) -> None:
        self.node_name_label.setText(text)

    def set_info_text(self, text: str) -> None:
        self.layer_info_text.setText(text)

    def set_action_buttons(self, buttons: list[QToolButton]) -> None:
        while self.action_buttons_container.count() > 0:
            self.action_buttons_container.takeAt(0)

        for button in buttons:
            self.action_buttons_container.addWidget(button)

    def update_node_data(self, node: Node) -> None: ...

    def cleanup(self) -> None: ...

    def apply(self, node_state: UiNodeState) -> None: ...
