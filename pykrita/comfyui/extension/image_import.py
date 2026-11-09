from krita import Document, Node
from PyQt5.QtGui import QImage

from comfyui.extension.layer_tree.utils import LayerUtils
from comfyui.extension.models import FlatLayerToken

_SRGB_PROFILES = ("sRGB-elle-V2-srgbtrc.icc", "sRGB built-in")


def insert_png_image(
    document: Document,
    image_data: bytes,
    path: list[FlatLayerToken],
    layer_name: str,
) -> Node:
    image = QImage.fromData(image_data, "PNG")
    if image.isNull():
        message = "The generated image payload is not a valid PNG"
        raise ValueError(message)

    # Krita's "RGBA" U8 paint device expects byte-ordered RGBA pixels.
    # ARGB32 is stored as BGRA on little-endian systems, so use Qt's explicit
    # byte-ordered RGBA format before passing the buffer to Node.setPixelData.
    image = image.convertToFormat(QImage.Format_RGBA8888)
    pixel_data = bytes(image.bits().asstring(image.byteCount()))
    expected_bytes = image.width() * image.height() * 4
    if len(pixel_data) < expected_bytes:
        message = f"Decoded PNG pixel buffer is incomplete: expected {expected_bytes} bytes, got {len(pixel_data)}"
        raise ValueError(message)

    node = document.createNode(layer_name, "paintLayer")
    if node is None:
        message = "Krita could not create a paint layer for the generated image"
        raise RuntimeError(message)

    if not any(node.setColorSpace("RGBA", "U8", profile) for profile in _SRGB_PROFILES):
        message = "Krita could not prepare an sRGB color space for the generated layer"
        raise RuntimeError(message)

    if not node.setPixelData(pixel_data, 0, 0, image.width(), image.height()):
        message = "Krita could not write the generated image pixels to the paint layer"
        raise RuntimeError(message)

    # PNG payload pixels are interpreted as sRGB, then converted into the
    # destination document's actual model, depth, and profile.
    LayerUtils.insert_node(document, node, path)
    parent = node.parentNode()
    if parent is None:
        message = "Krita reported a successful insertion but the generated layer has no parent"
        raise RuntimeError(message)

    if not node.setColorSpace(document.colorModel(), document.colorDepth(), document.colorProfile()):
        parent = node.parentNode()
        if parent is not None:
            parent.removeChildNode(node)
        message = "Krita could not convert the generated layer to the document color space"
        raise RuntimeError(message)

    document.refreshProjection()
    document.setModified(True)
    return node
