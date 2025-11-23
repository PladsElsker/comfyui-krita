from typing import ClassVar

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QPalette
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout

from ....layer_manager import LayerManager, PersistentLayerNotifier
from ....models import FlatLayerToken, Node, PersistentLayer
from ...icons import ARROW_DOWN_ICON, ARROW_UP_ICON, NO_VISIBILITY_ICON, SAVE_ICON, VISIBILITY_ICON, render_svg_to_pixmap
from .comfyui_node import ComfyUiNode
from .miniature import Miniature


class SaveImageNode(ComfyUiNode):
    type: ClassVar[str | None] = "KritaSaveImage-15347"

    def __init__(self, node: Node, layer_manager: LayerManager) -> None:  # noqa: PLR0915
        super().__init__(node, layer_manager)
        self.node_name = node.name
        self.layer_name: str = "Layer: "
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

        self.layer_info_text = QLabel(self.layer_name)
        self.layer_info_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.layer_info_text.setWordWrap(False)
        self.layer_info_text.setMinimumWidth(0)
        self.layer_info_text.setMaximumWidth(144)
        metrics = self.fontMetrics()
        elided = metrics.elidedText(node.name, Qt.TextElideMode.ElideRight, self.width())
        self.layer_info_text.setText(elided)
        self.middle_rack.addWidget(self.layer_info_text)

        self.main_layout.addLayout(self.middle_rack)
        self.main_layout.addStretch(1)

        self.action_buttons_container = QHBoxLayout()

        self.insert_below = True
        self.direction_button = QToolButton()
        self.direction_button.setAutoRaise(True)
        self.direction_button.setContentsMargins(0, 0, 0, 0)
        self.direction_button.clicked.connect(self._toggle_layer_direction)
        self._set_button_direction_below()
        self.action_buttons_container.addWidget(self.direction_button)

        self.show_linked_layer = True
        self.visibility_button = QToolButton()
        self.visibility_button.setAutoRaise(True)
        self.visibility_button.setContentsMargins(0, 0, 0, 0)
        self.visibility_button.clicked.connect(self._toggle_layer_visibility)
        self._set_button_visibility_on()
        self.action_buttons_container.addWidget(self.visibility_button)

        self.main_layout.addLayout(self.action_buttons_container)

        self._update_layer_name(node.name)
        self._create_layer()
        assert self.linked_layer is not None  # noqa: S101

        self.layer_notifier = self.layer_manager.notifier(self.linked_layer)
        self.layer_notifier.user_unrendered.connect(self._set_button_visibility_off)
        self.layer_notifier.name_changed.connect(self._update_layer_name)

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

    def _set_button_direction_below(self) -> None:
        self.insert_below = True
        self.direction_button.setToolTip("Toggle insert direction")
        palette = self.direction_button.palette()
        color = palette.color(QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(ARROW_UP_ICON, size=QSize(20, 20), color=color)

        if pixmap is not None:
            self.direction_button.setIconSize(pixmap.size())

        self.direction_button.setIcon(QIcon(pixmap))

    def _set_button_direction_above(self) -> None:
        self.insert_below = False
        self.direction_button.setToolTip("Toggle insert direction")
        palette = self.direction_button.palette()
        color = palette.color(QPalette.ColorRole.ButtonText)
        pixmap = render_svg_to_pixmap(ARROW_DOWN_ICON, size=QSize(20, 20), color=color)

        if pixmap is not None:
            self.direction_button.setIconSize(pixmap.size())

        self.direction_button.setIcon(QIcon(pixmap))

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

    def _update_layer_name(self, name: str) -> None:
        self.layer_name = name
        self.layer_info_text.setText(f'Layer: "{name}"')

    def _create_layer(self) -> None:
        if self.linked_layer is not None and self.layer_manager.exists(self.linked_layer):
            return

        name = self._generate_layer_name()
        path = self._generate_layer_path()
        self.linked_layer = self.layer_manager.create(name, path)

    def _generate_layer_name(self) -> str:
        return self.node_name

    def _generate_layer_path(self) -> list[FlatLayerToken] | None:
        return None
