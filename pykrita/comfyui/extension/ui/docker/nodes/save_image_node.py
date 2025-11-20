from PyQt5.QtWidgets import QHBoxLayout, QLabel

from ....models import Node
from ...icons import SAVE_ICON
from .comfyui_node import ComfyUiNode
from .miniature_label import MiniatureLabel


class SaveImageNode(ComfyUiNode):
    type: str | None = "KritaSaveImage-15347"

    def __init__(self, node: Node) -> None:
        super().__init__()
        self.main_layout = QHBoxLayout(self)

        self.miniature = MiniatureLabel(SAVE_ICON)
        self.miniature.pixmap()
        self.main_layout.addWidget(self.miniature)

        label = QLabel(f"{node.name} ({node.id})")
        self.main_layout.addWidget(label)
