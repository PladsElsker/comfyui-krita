from PyQt5.QtCore import QEvent, QObject, QSize
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ....models import Node
from ...icons import SAVE_ICON, TARGET_ICON, render_svg_to_pixmap
from .comfyui_node import ComfyUiNode
from .miniature import Miniature


class SaveImageNode(ComfyUiNode):
    type: str | None = "KritaSaveImage-15347"

    def __init__(self, node: Node) -> None:
        super().__init__(node)
        self.main_layout = QHBoxLayout(self)

        self.miniature = Miniature(SAVE_ICON)
        self.main_layout.addWidget(self.miniature)

        self.middle_rack = QVBoxLayout()
        label = QLabel(f"{node.name}")
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        self.middle_rack.addWidget(label)

        self.combo_box = QComboBox()
        self.combo_box.addItems(["Generate Layers Below", " Generate Layers Above"])
        self._wheel_filter = WheelFilter(self)
        self.combo_box.installEventFilter(self._wheel_filter)
        self.middle_rack.addWidget(self.combo_box)

        self.main_layout.addLayout(self.middle_rack)

        self.action_buttons_container = QHBoxLayout()
        self.target_button = QToolButton()
        self.target_button.setAutoRaise(True)
        pixmap = render_svg_to_pixmap(TARGET_ICON, size=QSize(20, 20), color=QColor(192, 192, 192))
        self.target_button.setIcon(QIcon(pixmap))
        if pixmap is not None:
            self.target_button.setIconSize(pixmap.size())
        self.target_button.setToolTip("Select layer generator")
        self.action_buttons_container.addWidget(self.target_button)

        self.main_layout.addLayout(self.action_buttons_container)


class WheelFilter(QObject):
    def __init__(self, combo: QComboBox) -> None:
        super().__init__(combo)
        self.combo = combo

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:  # noqa: N802
        if a1 is None:
            return True

        if (a1.type() == QEvent.Type.Wheel and isinstance(a0, QWidget)) and (a0 is self.combo or self.combo.isAncestorOf(a0)):
            return not self.combo.hasFocus()

        return False
