from PyQt5.QtWidgets import QWidget

from ....models import Node


class ComfyUiNode(QWidget):
    type: str | None = None

    def __init__(self, node: Node) -> None:  # noqa: ARG002
        super().__init__()
