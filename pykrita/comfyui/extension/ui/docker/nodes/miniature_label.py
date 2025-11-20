from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QLabel

from ...icons import render_svg_to_pixmap


class MiniatureLabel(QLabel):
    def __init__(self, svg_renderer: QSvgRenderer) -> None:
        super().__init__()
        self.setFixedSize(32, 32)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background-color: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 2px; color: #666;",
        )
        self.svg_renderer = svg_renderer
        self.setPixmap(render_svg_to_pixmap(self.svg_renderer))

    def set_image(self, data: bytes | None) -> None:
        if data:
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.setPixmap(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.setText("")
                return

        self.setPixmap(render_svg_to_pixmap(self.svg_renderer))
