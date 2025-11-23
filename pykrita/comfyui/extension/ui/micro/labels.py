from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QResizeEvent
from PyQt5.QtWidgets import QLabel


class ElidedLabel(QLabel):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self._raw_text = text
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.setWordWrap(False)
        self.setMinimumWidth(0)
        self.setMaximumWidth(144)
        self._apply_elide()

    def setText(self, a0: str | None) -> None:  # noqa: N802
        self._raw_text = a0
        self._apply_elide()

    def resizeEvent(self, a0: QResizeEvent | None) -> None:  # noqa: N802
        self._apply_elide()
        super().resizeEvent(a0)

    def _apply_elide(self) -> None:
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self._raw_text, Qt.TextElideMode.ElideRight, self.width())
        super().setText(elided)


class NodeTitleLabel(ElidedLabel):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        f = self.font()
        f.setBold(True)
        self.setFont(f)


class NodeDescriptionLabel(ElidedLabel):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        palette = self.palette()
        disabled_color = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText)
        self.setStyleSheet(f"color: {disabled_color.name()};")
