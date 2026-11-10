from krita import Document, Node
from PyQt5.QtGui import QImage

from comfyui.extension.layer_tree.utils import LayerUtils
from comfyui.extension.models import FlatLayerToken

_SRGB_PROFILES = ("sRGB-elle-V2-srgbtrc.icc", "sRGB built-in")


def _set_srgb_color_space(node: Node) -> bool:
    return any(node.setColorSpace("RGBA", "U8", profile) for profile in _SRGB_PROFILES)


def _decode_png(image_data: bytes) -> tuple[int, int, bytes]:
    image = QImage.fromData(image_data, "PNG")
    if image.isNull():
        message = "The generated image payload is not a valid PNG"
        raise ValueError(message)

    # Krita's paint-device buffer uses QImage's native ARGB32 byte layout.
    # This matches the conversion used by established Krita integrations.
    image = image.convertToFormat(QImage.Format_ARGB32)
    width = image.width()
    height = image.height()
    pixel_data = bytes(image.bits().asstring(image.byteCount()))
    expected_bytes = width * height * 4
    if len(pixel_data) != expected_bytes:
        message = f"Decoded PNG pixel buffer has {len(pixel_data)} bytes; expected {expected_bytes}"
        raise ValueError(message)

    return width, height, pixel_data


def _create_populated_layer(
    document: Document,
    layer_name: str,
    width: int,
    height: int,
    pixel_data: bytes,
) -> Node:
    node = document.createNode(layer_name, "paintlayer")
    if node is None:
        message = "Krita could not create a paint layer for the generated image"
        raise RuntimeError(message)

    source_color_space = _set_srgb_color_space(node)
    if not source_color_space:
        message = "Krita could not prepare an sRGB color space for the generated layer"
        raise RuntimeError(message)

    pixel_write_result = node.setPixelData(pixel_data, 0, 0, width, height)
    # Krita 5.2.x shipped a SIP declaration that exposed this bool-returning
    # C++ method as void, so Python receives None even when the write succeeds.
    # Only an explicit False is a failed write; None must be verified by readback.
    if pixel_write_result is False:
        message = "Krita rejected the generated image pixel buffer"
        raise RuntimeError(message)

    written_pixels = bytes(node.pixelData(0, 0, width, height))
    expected_bytes = width * height * 4
    if len(written_pixels) != expected_bytes:
        message = f"Krita stored {len(written_pixels)} bytes for the generated layer; expected {expected_bytes}"
        raise RuntimeError(message)

    if written_pixels != pixel_data:
        first_mismatch = next(
            (index for index, (actual, expected) in enumerate(zip(written_pixels, pixel_data, strict=True)) if actual != expected),
            None,
        )
        message = "Krita pixel readback does not match the generated PNG pixel buffer"
        raise RuntimeError(message)


    return node


def insert_png_image(
    document: Document,
    image_data: bytes,
    path: list[FlatLayerToken],
    layer_name: str,
) -> Node:
    width, height, pixel_data = _decode_png(image_data)
    node = _create_populated_layer(document, layer_name, width, height, pixel_data)

    # Keep the existing target-resolution/rebasing implementation intact.
    LayerUtils.insert_node(document, node, path)
    parent = node.parentNode()
    if parent is None:
        message = "Krita did not attach the generated layer to the document"
        raise RuntimeError(message)

    color_conversion = node.setColorSpace(document.colorModel(), document.colorDepth(), document.colorProfile())
    if not color_conversion:
        message = (
            "Krita could not convert the generated layer into the document color space "
            f"({document.colorModel()}, {document.colorDepth()}, {document.colorProfile()})"
        )
        raise RuntimeError(message)

    node.setVisible(True)
    document.setActiveNode(node)
    active_node = document.activeNode()
    document.refreshProjection()
    document.setModified(True)

    final_parent = node.parentNode()
    if final_parent is None:
        message = "The generated layer became detached during color conversion"
        raise RuntimeError(message)

    return node
