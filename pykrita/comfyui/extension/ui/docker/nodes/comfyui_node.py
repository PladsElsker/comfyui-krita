from PyQt5.QtWidgets import QWidget

from ....models import Node, NodeDirection


class ComfyUiNode(QWidget):
    type: str | None = None
    direction: NodeDirection | None

    def __init__(self, node: Node) -> None:
        super().__init__()
        self.direction = node.direction
