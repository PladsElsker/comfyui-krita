from typing import cast

from PyQt5.QtCore import QSize, pyqtBoundSignal, pyqtSignal
from PyQt5.QtGui import QIcon, QPalette
from PyQt5.QtWidgets import QToolButton

from comfyui.extension.ui.icons import ARROW_DOWN_ICON, ARROW_UP_ICON, NO_VISIBILITY_ICON, VISIBILITY_ICON, render_svg_to_pixmap


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


class VisibilityButton(QToolButton):
    changed_to_visible = cast("pyqtBoundSignal", pyqtSignal())
    changed_to_hidden = cast("pyqtBoundSignal", pyqtSignal())

    def __init__(self, visible: bool = True) -> None:  # noqa: FBT002
        super().__init__()
        self._show_layer = visible
        self.setAutoRaise(True)
        self.setContentsMargins(0, 0, 0, 0)
        self.clicked.connect(self._toggle)
        if visible:
            self._set_visibility_on()
        else:
            self._set_visibility_off()

    def _toggle(self) -> None:
        self._show_layer = not self._show_layer

        if self._show_layer:
            self._set_visibility_on()
        else:
            self._set_visibility_off()

    def set_visibility_on_visual(self) -> None:
        self._show_layer = True
        self.setToolTip("Hide linked layer")
        color = self.palette().color(QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(VISIBILITY_ICON, QSize(20, 20), color=color)

        if pixmap:
            self.setIconSize(pixmap.size())
            self.setIcon(QIcon(pixmap))

    def set_visibility_off_visual(self) -> None:
        self._show_layer = False
        self.setToolTip("Show linked layer")
        color = self.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(NO_VISIBILITY_ICON, QSize(20, 20), color=color)

        if pixmap:
            self.setIconSize(pixmap.size())
            self.setIcon(QIcon(pixmap))

    def _set_visibility_on(self) -> None:
        self.set_visibility_on_visual()
        self.changed_to_visible.emit()

    def _set_visibility_off(self) -> None:
        self.set_visibility_off_visual()
        self.changed_to_hidden.emit()
