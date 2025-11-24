from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QPixmap
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication, QLabel

from comfyui.extension.ui.icons import render_svg_to_pixmap


class Miniature(QLabel):
    def __init__(self, svg_renderer: QSvgRenderer) -> None:
        super().__init__()
        self.setFixedSize(32, 32)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        palette = QApplication.palette()
        bg_color = palette.color(QPalette.ColorRole.Base)
        border_color = palette.color(QPalette.ColorRole.Dark)
        text_color = palette.color(QPalette.ColorRole.Text)
        self.setStyleSheet(
            f"""
            background-color: {bg_color.name()};
            border: 1px solid {border_color.name()};
            border-radius: 2px;
            color: {text_color.name()};
            """,
        )
        self.svg_renderer = svg_renderer
        self.setPixmap(render_svg_to_pixmap(self.svg_renderer))

    def set_image(self, data: bytes) -> None:
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.setPixmap(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def remove_image(self) -> None:
        self.setPixmap(render_svg_to_pixmap(self.svg_renderer))
