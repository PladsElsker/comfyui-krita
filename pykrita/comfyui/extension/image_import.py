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

    image = image.convertToFormat(QImage.Format_ARGB32)
    pixel_data = bytes(image.bits().asstring(image.byteCount()))

    node = document.createNode(layer_name, "paintlayer")
    if node is None:
        message = "Krita could not create a paint layer for the generated image"
        raise RuntimeError(message)

    if not any(node.setColorSpace("RGBA", "U8", profile) for profile in _SRGB_PROFILES):
        message = "Krita could not assign an sRGB color space to the generated layer"
        raise RuntimeError(message)

    LayerUtils.insert_node(document, node, path)

    if not node.setPixelData(pixel_data, 0, 0, image.width(), image.height()):
        parent = node.parentNode()
        if parent is not None:
            parent.removeChildNode(node)
        message = "Krita could not write the generated image pixels to the paint layer"
        raise RuntimeError(message)

    document.refreshProjection()
    document.setModified(True)
    return node
