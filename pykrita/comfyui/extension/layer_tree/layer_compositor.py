from dataclasses import dataclass, field

from PyQt5.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PyQt5.QtGui import QImage, QPainter


@dataclass(frozen=True)
class LayerGroupSnapshot:
    node_id: str
    opacity: int
    blending_mode: str


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
    ancestors: tuple[LayerGroupSnapshot, ...] = ()


@dataclass
class _CompositeGroup:
    snapshot: LayerGroupSnapshot
    children: list[object] = field(default_factory=list)


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
    """Composite detached Krita pixel buffers without accessing Krita objects."""
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError("The Krita document canvas has invalid dimensions")
    if not snapshots:
        raise ValueError("No visible layer pixels were captured")

    root_entries = _build_composite_tree(snapshots)
    composite = QImage(canvas_width, canvas_height, QImage.Format.Format_ARGB32_Premultiplied)
    composite.fill(Qt.GlobalColor.transparent)
    _draw_entries(composite, root_entries)

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


def _build_composite_tree(snapshots: list[LayerPixelSnapshot]) -> list[object]:
    root_entries: list[object] = []
    children_by_path: dict[tuple[str, ...], list[object]] = {(): root_entries}
    groups_by_path: dict[tuple[str, ...], _CompositeGroup] = {}

    for snapshot in snapshots:
        path: tuple[str, ...] = ()
        for group_snapshot in snapshot.ancestors:
            path = (*path, group_snapshot.node_id)
            if path not in groups_by_path:
                group = _CompositeGroup(group_snapshot)
                groups_by_path[path] = group
                children_by_path[path[:-1]].append(group)
                children_by_path[path] = group.children
        children_by_path[path].append(snapshot)

    return root_entries


def _draw_entries(target: QImage, entries: list[object]) -> None:
    painter = QPainter(target)
    if not painter.isActive():
        raise RuntimeError("Could not initialize the in-memory layer compositor")

    try:
        for entry in entries:
            if isinstance(entry, _CompositeGroup):
                group_image = QImage(
                    target.width(),
                    target.height(),
                    QImage.Format.Format_ARGB32_Premultiplied,
                )
                group_image.fill(Qt.GlobalColor.transparent)
                _draw_entries(group_image, entry.children)
                _draw_image(
                    painter,
                    group_image,
                    0,
                    0,
                    entry.snapshot.opacity,
                    entry.snapshot.blending_mode,
                    entry.snapshot.node_id,
                )
            elif isinstance(entry, LayerPixelSnapshot):
                expected_bytes = entry.width * entry.height * 4
                if entry.width <= 0 or entry.height <= 0 or len(entry.pixels) != expected_bytes:
                    raise ValueError(f"Layer {entry.name!r} has an invalid RGBA pixel buffer")

                # Krita integer RGBA projections are stored in BGRA byte order;
                # QImage.Format_ARGB32 uses that native byte layout on Qt's
                # supported little-endian desktop platforms.
                image = QImage(
                    entry.pixels,
                    entry.width,
                    entry.height,
                    entry.width * 4,
                    QImage.Format.Format_ARGB32,
                ).copy()
                if image.isNull():
                    raise RuntimeError(f"Could not construct a pixel image for layer {entry.name!r}")

                _draw_image(
                    painter,
                    image,
                    entry.x,
                    entry.y,
                    entry.opacity,
                    entry.blending_mode,
                    entry.name,
                )
            else:
                raise TypeError(f"Unexpected in-memory layer entry: {type(entry).__name__}")
    finally:
        painter.end()


def _draw_image(
    painter: QPainter,
    image: QImage,
    x: int,
    y: int,
    opacity: int,
    blending_mode: str,
    name: str,
) -> None:
    mode_key = blending_mode.strip().lower()
    composition_mode = _COMPOSITION_MODES.get(mode_key)
    if composition_mode is None:
        raise ValueError(
            f"Layer/group {name!r} uses the unsupported Krita blending mode {blending_mode!r}"
        )

    painter.save()
    try:
        painter.setCompositionMode(composition_mode)
        painter.setOpacity(max(0, min(opacity, 255)) / 255.0)
        painter.drawImage(x, y, image)
    finally:
        painter.restore()
