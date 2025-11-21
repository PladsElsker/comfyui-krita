from typing import ClassVar

from PyQt5.QtCore import QEvent, QObject, QSize, Qt
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ....layers_manager import PersistentLayerManager
from ....models import Node
from ...icons import SAVE_ICON, TARGET_ICON, render_svg_to_pixmap
from .comfyui_node import ComfyUiNode
from .miniature import Miniature

COMBO_ABOVE_TEXT = "Insert Layers Above"
COMBO_BELOW_TEXT = "Insert Layers Below"
ARROW_UP = "▲"
ARROW_DOWN = "▼"


class SaveImageNode(ComfyUiNode):
    type: ClassVar[str | None] = "KritaSaveImage-15347"

    def __init__(self, node: Node, layers_manager: PersistentLayerManager) -> None:
        super().__init__(node, layers_manager)
        self.node_name = node.name
        self.linked_layer = None

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 0, 0)

        self.miniature = Miniature(SAVE_ICON)
        self.main_layout.addWidget(self.miniature)

        self.middle_rack = QVBoxLayout()
        label = QLabel(node.name)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        label.setWordWrap(False)
        label.setMinimumWidth(0)
        label.setMaximumWidth(144)
        metrics = self.fontMetrics()
        elided = metrics.elidedText(node.name, Qt.TextElideMode.ElideRight, self.width())
        label.setText(elided)
        self.middle_rack.addWidget(label)

        self.combo_box = QComboBox()
        self.combo_box.addItems([COMBO_BELOW_TEXT, COMBO_ABOVE_TEXT])
        self._wheel_filter = WheelFilter(self)
        self.combo_box.installEventFilter(self._wheel_filter)
        self.combo_box.currentTextChanged.connect(self._update_layer_name)
        self.middle_rack.addWidget(self.combo_box)

        self.main_layout.addLayout(self.middle_rack)

        self.action_buttons_container = QHBoxLayout()
        self.target_button = QToolButton()
        self.target_button.setAutoRaise(True)
        pixmap = render_svg_to_pixmap(TARGET_ICON, size=QSize(20, 20), color=QColor(192, 192, 192))
        self.target_button.setIcon(QIcon(pixmap))

        if pixmap is not None:
            self.target_button.setIconSize(pixmap.size())

        self.target_button.setToolTip("Locate linked layer")
        self.action_buttons_container.addWidget(self.target_button)
        self.target_button.clicked.connect(self._locate_layer)

        self.main_layout.addLayout(self.action_buttons_container)

        self._create_layer()

    def cleanup(self) -> None:
        self.layers_manager.delete(self.linked_layer)

    def _locate_layer(self) -> None:
        if self.layers_manager.exists(self.linked_layer):
            self.layers_manager.select(self.linked_layer)
        else:
            self._create_layer()
            self.layers_manager.select(self.linked_layer)

    def _create_layer(self) -> None:
        if self.layers_manager.exists(self.linked_layer):
            return

        name = self._generate_layer_name()
        self.linked_layer = self.layers_manager.create(name)

    def _update_layer_name(self) -> None:
        if self.layers_manager.exists(self.linked_layer):
            name = self._generate_layer_name()
            self.layers_manager.rename(self.linked_layer, name)
        else:
            self._create_layer()

    def _generate_layer_name(self) -> str:
        arrow = ARROW_DOWN if self.combo_box.currentText() == COMBO_BELOW_TEXT else ARROW_UP
        return f"{self.node_name} {arrow}"


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
