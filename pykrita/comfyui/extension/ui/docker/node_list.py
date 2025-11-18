from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...models import Node  # noqa: TID252


class NodeListWidget(QWidget):
    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.labels = []

    def rebuild(self, nodes: list[Node]) -> None:
        while self.main_layout.count() > 0:
            item = self.main_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        self.labels.clear()

        for node in nodes:
            label = QLabel(f"{node.type} ({node.id})")
            self.main_layout.insertWidget(self.main_layout.count() - 1, label)
            self.labels.append(label)
