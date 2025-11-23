from pathlib import Path

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

current_file = Path(__file__).resolve()
icon_path = current_file.parent / "layers.svg"

LAYERS_ICON = QSvgRenderer(str(current_file.parent / "layers.svg"))
SAVE_ICON = QSvgRenderer(str(current_file.parent / "save.svg"))
TARGET_ICON = QSvgRenderer(str(current_file.parent / "target.svg"))
VISIBILITY_ICON = QSvgRenderer(str(current_file.parent / "visibility.svg"))
NO_VISIBILITY_ICON = QSvgRenderer(str(current_file.parent / "visibility_off.svg"))
ARROW_UP_ICON = QSvgRenderer(str(current_file.parent / "arrow_up.svg"))
ARROW_DOWN_ICON = QSvgRenderer(str(current_file.parent / "arrow_down.svg"))


def render_svg_to_pixmap(
    renderer: QSvgRenderer,
    size: QSize | tuple[int, int] | None = None,
    color: QColor | None = None,
) -> QPixmap:
    if size is None:
        size = renderer.defaultSize()
    elif isinstance(size, tuple):
        size = QSize(*size)

    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    if color is None:
        color = QColor(150, 150, 150)

    tinted = QPixmap(pixmap.size())
    tinted.fill(Qt.GlobalColor.transparent)

    p = QPainter(tinted)
    p.drawPixmap(0, 0, pixmap)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(tinted.rect(), color)
    p.end()

    return tinted
