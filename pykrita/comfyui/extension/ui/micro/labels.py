from collections.abc import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPaintEvent, QPalette
from PyQt5.QtWidgets import QLabel


class ElidedLabel(QLabel):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.get_width_fun: Callable[[], int] = self.width
        self._raw_text = text
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.setWordWrap(False)
        self._apply_elide()

    def set_elided_width_producer(self, get_width: Callable[[], int]) -> None:
        self.get_width_fun = get_width

    def setText(self, a0: str | None) -> None:  # noqa: N802
        self._raw_text = a0
        self._apply_elide()

    def paintEvent(self, a0: QPaintEvent | None) -> None:  # noqa: N802
        self._apply_elide()
        super().paintEvent(a0)

    def _apply_elide(self) -> None:
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self._raw_text, Qt.TextElideMode.ElideRight, self.get_width_fun())
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
