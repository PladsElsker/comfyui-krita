from dataclasses import dataclass

from PyQt5.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PyQt5.QtGui import QImage, QPainter


@dataclass(frozen=True)
class LayerPixelSnapshot:
    name: str
    x: int
    y: int
    width: int
    height: int
    pixels: bytes
    opacity: int
    blending_mode: str


_COMPOSITION_MODES = {
    "normal": QPainter.CompositionMode.CompositionMode_SourceOver,
    "normal (all)": QPainter.CompositionMode.CompositionMode_SourceOver,
    "multiply": QPainter.CompositionMode.CompositionMode_Multiply,
    "screen": QPainter.CompositionMode.CompositionMode_Screen,
    "overlay": QPainter.CompositionMode.CompositionMode_Overlay,
    "darken": QPainter.CompositionMode.CompositionMode_Darken,
    "lighten": QPainter.CompositionMode.CompositionMode_Lighten,
    "colordodge": QPainter.CompositionMode.CompositionMode_ColorDodge,
    "color dodge": QPainter.CompositionMode.CompositionMode_ColorDodge,
    "colorburn": QPainter.CompositionMode.CompositionMode_ColorBurn,
    "color burn": QPainter.CompositionMode.CompositionMode_ColorBurn,
    "hardlight": QPainter.CompositionMode.CompositionMode_HardLight,
    "hard light": QPainter.CompositionMode.CompositionMode_HardLight,
    "softlight": QPainter.CompositionMode.CompositionMode_SoftLight,
    "soft light": QPainter.CompositionMode.CompositionMode_SoftLight,
    "difference": QPainter.CompositionMode.CompositionMode_Difference,
    "exclusion": QPainter.CompositionMode.CompositionMode_Exclusion,
    "addition": QPainter.CompositionMode.CompositionMode_Plus,
    "add": QPainter.CompositionMode.CompositionMode_Plus,
}


def composite_layer_snapshots(
    canvas_width: int,
    canvas_height: int,
    snapshots: list[LayerPixelSnapshot],
) -> bytes:
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError("The Krita document canvas has invalid dimensions")
    if not snapshots:
        raise ValueError("No visible layer pixels were captured")

    composite = QImage(canvas_width, canvas_height, QImage.Format.Format_ARGB32_Premultiplied)
    composite.fill(Qt.GlobalColor.transparent)

    painter = QPainter(composite)
    if not painter.isActive():
        raise RuntimeError("Could not initialize the in-memory layer compositor")

    try:
        for snapshot in snapshots:
            expected_bytes = snapshot.width * snapshot.height * 4
            if snapshot.width <= 0 or snapshot.height <= 0 or len(snapshot.pixels) != expected_bytes:
                raise ValueError(f"Layer {snapshot.name!r} has an invalid RGBA pixel buffer")

            mode_key = snapshot.blending_mode.strip().lower()
            composition_mode = _COMPOSITION_MODES.get(mode_key)
            if composition_mode is None:
                raise ValueError(
                    f"Layer {snapshot.name!r} uses the unsupported Krita blending mode "
                    f"{snapshot.blending_mode!r}"
                )

            image = QImage(
                snapshot.pixels,
                snapshot.width,
                snapshot.height,
                snapshot.width * 4,
                QImage.Format.Format_ARGB32,
            ).copy()
            if image.isNull():
                raise RuntimeError(f"Could not construct a pixel image for layer {snapshot.name!r}")

            painter.setCompositionMode(composition_mode)
            painter.setOpacity(max(0, min(snapshot.opacity, 255)) / 255.0)
            painter.drawImage(snapshot.x, snapshot.y, image)
    finally:
        painter.end()

    buffer_data = QByteArray()
    buffer = QBuffer(buffer_data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Could not open the in-memory PNG buffer")
    try:
        if not composite.save(buffer, "PNG"):
            raise RuntimeError("Could not encode the composite as PNG")
    finally:
        buffer.close()

    result = bytes(buffer_data)
    if not result:
        raise RuntimeError("The in-memory layer compositor produced an empty PNG")
    return result
