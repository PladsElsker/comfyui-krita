from typing import cast

from PyQt5.QtCore import QSize, pyqtBoundSignal, pyqtSignal
from PyQt5.QtGui import QIcon, QPalette
from PyQt5.QtWidgets import QStyle, QToolButton

from comfyui.extension.ui.icons import ARROW_DOWN_ICON, ARROW_UP_ICON, EDIT_ICON, render_svg_to_pixmap


class DirectionButton(QToolButton):
    changed_to_above = cast("pyqtBoundSignal", pyqtSignal())
    changed_to_below = cast("pyqtBoundSignal", pyqtSignal())

    def __init__(self, insert_below: bool = True) -> None:  # noqa: FBT002
        super().__init__()
        self._insert_below = insert_below
        self.setAutoRaise(True)
        self.setContentsMargins(0, 0, 0, 0)
        self.clicked.connect(self._toggle)

        if insert_below:
            self._set_below_icon()
        else:
            self._set_above_icon()

    def is_inserting_below(self) -> bool:
        return self._insert_below

    def toggle_state(self) -> None:
        self._toggle()

    def _toggle(self) -> None:
        self._insert_below = not self._insert_below

        if self._insert_below:
            self._set_below_icon()
        else:
            self._set_above_icon()

    def _set_below_icon(self) -> None:
        self.setToolTip("Toggle insert direction")
        color = self.palette().color(QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(ARROW_DOWN_ICON, size=QSize(20, 20), color=color)

        if pixmap:
            self.setIconSize(pixmap.size())
            self.setIcon(QIcon(pixmap))

        self.changed_to_below.emit()

    def _set_above_icon(self) -> None:
        self.setToolTip("Toggle insert direction")
        color = self.palette().color(QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(ARROW_UP_ICON, size=QSize(20, 20), color=color)

        if pixmap:
            self.setIconSize(pixmap.size())
            self.setIcon(QIcon(pixmap))

        self.changed_to_above.emit()


class TargetEditButton(QToolButton):
    """Edit/cancel control replacing the former visibility button in-place."""

    def __init__(self) -> None:
        super().__init__()
        self.setAutoRaise(True)
        self.setContentsMargins(0, 0, 0, 0)
        self.set_editing(False)

    def set_editing(self, editing: bool) -> None:
        if editing:
            self.setToolTip(
                "Click a layer in Krita's Layers Docker to set it as the output target.\n"
                "Click this button again to cancel target editing."
            )
            self.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))
            return

        self.setToolTip("Edit target")
        color = self.palette().color(QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(EDIT_ICON, size=QSize(20, 20), color=color)

        if pixmap:
            self.setIconSize(pixmap.size())
            self.setIcon(QIcon(pixmap))
