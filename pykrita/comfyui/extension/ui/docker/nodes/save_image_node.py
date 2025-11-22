from typing import ClassVar

from PyQt5.QtCore import QEvent, QObject, QSize, Qt
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ....layers_manager import PersistentLayerManager
from ....models import FlatLayerToken, Node, PersistentLayer
from ...icons import NO_VISIBILITY_ICON, SAVE_ICON, VISIBILITY_ICON, render_svg_to_pixmap
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
        self.linked_layer: PersistentLayer | None = None

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

        self.show_linked_layer = True
        self.action_buttons_container = QHBoxLayout()
        self.visibility_button = QToolButton()
        self.visibility_button.setAutoRaise(True)
        self._set_button_visibility_on()
        self.action_buttons_container.addWidget(self.visibility_button)
        self.visibility_button.clicked.connect(self._toggle_layer_visibility)

        self.main_layout.addLayout(self.action_buttons_container)

        self._create_layer()

    def cleanup(self) -> None:
        if self.linked_layer is None:
            return

        self.layers_manager.delete(self.linked_layer)

    def _toggle_layer_visibility(self) -> None:
        self.show_linked_layer = not self.show_linked_layer

        if self.linked_layer is None or not self.layers_manager.exists(self.linked_layer):
            self._create_layer()

        assert self.linked_layer is not None  # noqa: S101

        if self.show_linked_layer:
            self._set_button_visibility_on()
            self.layers_manager.show(self.linked_layer)
        else:
            self._set_button_visibility_off()
            self.layers_manager.hide(self.linked_layer)

    def _set_button_visibility_on(self) -> None:
        self.visibility_button.setToolTip("Hide linked layer")
        pixmap = render_svg_to_pixmap(VISIBILITY_ICON, size=QSize(20, 20), color=QColor(192, 192, 192))

        if pixmap is not None:
            self.visibility_button.setIconSize(pixmap.size())

        self.visibility_button.setIcon(QIcon(pixmap))

    def _set_button_visibility_off(self) -> None:
        self.visibility_button.setToolTip("Show linked layer")
        pixmap = render_svg_to_pixmap(NO_VISIBILITY_ICON, size=QSize(20, 20), color=QColor(192, 192, 192))

        if pixmap is not None:
            self.visibility_button.setIconSize(pixmap.size())

        self.visibility_button.setIcon(QIcon(pixmap))

    def _update_layer_name(self) -> None:
        if self.linked_layer is not None and self.layers_manager.exists(self.linked_layer):
            name = self._generate_layer_name()
            self.layers_manager.rename(self.linked_layer, name)
        else:
            self._create_layer()

    def _create_layer(self) -> None:
        if self.linked_layer is not None and self.layers_manager.exists(self.linked_layer):
            return

        name = self._generate_layer_name()
        path = self._generate_layer_path()
        self.linked_layer = self.layers_manager.create(name, path)

    def _generate_layer_name(self) -> str:
        arrow = ARROW_DOWN if self.combo_box.currentText() == COMBO_BELOW_TEXT else ARROW_UP
        return f"{self.node_name} {arrow}"

    def _generate_layer_path(self) -> list[FlatLayerToken] | None:
        return None


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
