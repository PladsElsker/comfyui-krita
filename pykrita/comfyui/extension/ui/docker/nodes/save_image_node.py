from typing import ClassVar

from PyQt5.QtCore import QEvent, QObject, QSize, Qt
from PyQt5.QtGui import QIcon, QPalette
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ....layer_manager import LayerManager, PersistentLayerNotifier
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

    def __init__(self, node: Node, layer_manager: LayerManager) -> None:
        super().__init__(node, layer_manager)
        self.node_name = node.name
        self.linked_layer: PersistentLayer | None = None
        self.layer_notifier: PersistentLayerNotifier | None = None

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 0, 0)

        self.miniature = Miniature(SAVE_ICON)
        self.main_layout.addWidget(self.miniature)

        self.middle_rack = QVBoxLayout()
        self.node_name_label = QLabel(node.name)
        font = self.node_name_label.font()
        font.setBold(True)
        self.node_name_label.setFont(font)
        self.node_name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.node_name_label.setWordWrap(False)
        self.node_name_label.setMinimumWidth(0)
        self.node_name_label.setMaximumWidth(144)
        metrics = self.fontMetrics()
        elided = metrics.elidedText(node.name, Qt.TextElideMode.ElideRight, self.width())
        self.node_name_label.setText(elided)
        self.middle_rack.addWidget(self.node_name_label)

        self.combo_box = QComboBox()
        self.combo_box.addItems([COMBO_BELOW_TEXT, COMBO_ABOVE_TEXT])
        self._wheel_filter = WheelFilter(self)
        self.combo_box.installEventFilter(self._wheel_filter)
        self.combo_box.currentTextChanged.connect(self._update_layer_name)
        self.middle_rack.addWidget(self.combo_box)

        self.main_layout.addLayout(self.middle_rack)

        self.insert_below = True
        self.direction_button = QToolButton()
        self.direction_button.setAutoRaise(True)
        self.direction_button.clicked.connect(self._toggle_layer_direction)
        self._set_button_direction_below()
        self.action_buttons_container.addWidget(self.direction_button)

        self.show_linked_layer = True
        self.action_buttons_container = QHBoxLayout()
        self.visibility_button = QToolButton()
        self.visibility_button.setAutoRaise(True)
        self.visibility_button.clicked.connect(self._toggle_layer_visibility)
        self._set_button_visibility_on()
        self.action_buttons_container.addWidget(self.visibility_button)

        self.main_layout.addLayout(self.action_buttons_container)

        self._create_layer()
        assert self.linked_layer is not None  # noqa: S101

        self.layer_notifier = self.layer_manager.notifier(self.linked_layer)
        self.layer_notifier.user_unrendered.connect(self._set_button_visibility_off)

    def cleanup(self) -> None:
        if self.linked_layer is None:
            return

        self.layer_manager.delete(self.linked_layer)

    def _toggle_layer_direction(self) -> None:
        self.insert_below = not self.insert_below

        if self.insert_below:
            self._set_button_direction_below()
        else:
            self._set_button_direction_above()

    def _toggle_layer_visibility(self) -> None:
        self.show_linked_layer = not self.show_linked_layer

        if self.linked_layer is None or not self.layer_manager.exists(self.linked_layer):
            self._create_layer()

        assert self.linked_layer is not None  # noqa: S101

        if self.show_linked_layer:
            self._set_button_visibility_on()
            self.layer_manager.show(self.linked_layer)
        else:
            self._set_button_visibility_off()
            self.layer_manager.hide(self.linked_layer)

    def _set_button_visibility_on(self) -> None:
        self.show_linked_layer = True
        self.visibility_button.setToolTip("Hide linked layer")
        palette = self.visibility_button.palette()
        color = palette.color(QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(VISIBILITY_ICON, size=QSize(20, 20), color=color)

        if pixmap is not None:
            self.visibility_button.setIconSize(pixmap.size())

        self.visibility_button.setIcon(QIcon(pixmap))

    def _set_button_visibility_off(self) -> None:
        self.show_linked_layer = False
        self.visibility_button.setToolTip("Show linked layer")
        palette = self.visibility_button.palette()
        color = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(NO_VISIBILITY_ICON, size=QSize(20, 20), color=color)

        if pixmap is not None:
            self.visibility_button.setIconSize(pixmap.size())

        self.visibility_button.setIcon(QIcon(pixmap))

    def _update_layer_name(self) -> None:
        if self.linked_layer is not None and self.layer_manager.exists(self.linked_layer):
            name = self._generate_layer_name()
            self.layer_manager.rename(self.linked_layer, name)
        else:
            self._create_layer()

    def _create_layer(self) -> None:
        if self.linked_layer is not None and self.layer_manager.exists(self.linked_layer):
            return

        name = self._generate_layer_name()
        path = self._generate_layer_path()
        self.linked_layer = self.layer_manager.create(name, path)

    def _generate_layer_name(self) -> str:
        arrow = ARROW_DOWN if self.combo_box.currentText() == COMBO_BELOW_TEXT else ARROW_UP
        return f"ComfyUI: {self.node_name} {arrow}"

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
