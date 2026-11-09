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

    # Krita's Node.setPixelData() expects the native ARGB32 byte layout for
    # its RGBA paint-device format (BGRA bytes on little-endian systems).
    # This matches Krita AI Diffusion's Image.to_krita_format() convention.
    image = image.convertToFormat(QImage.Format_ARGB32)
    width = image.width()
    height = image.height()
    pixel_data = bytes(image.bits().asstring(image.byteCount()))
    expected_bytes = width * height * 4
    if len(pixel_data) != expected_bytes:
        message = f"Decoded PNG pixel buffer has {len(pixel_data)} bytes; expected {expected_bytes}"
        raise ValueError(message)

    node = document.createNode(layer_name, "paintlayer")
    if node is None:
        message = "Krita could not create a paint layer for the generated image"
        raise RuntimeError(message)

    try:
        # Attach the node first. Krita's color-space conversion and paint-device
        # writes are then performed against a node that is part of the document.
        LayerUtils.insert_node(document, node, path)
        parent = node.parentNode()
        if parent is None:
            message = "Krita did not attach the generated layer to the document"
            raise RuntimeError(message)

        source_profile = next(
            (
                profile
                for profile in _SRGB_PROFILES
                if node.setColorSpace("RGBA", "U8", profile)
            ),
            None,
        )
        if source_profile is None:
            message = "Krita could not prepare an sRGB color space for the generated layer"
            raise RuntimeError(message)

        if not node.setPixelData(pixel_data, 0, 0, width, height):
            message = "Krita rejected the generated image pixel buffer"
            raise RuntimeError(message)

        written_pixels = node.pixelData(0, 0, width, height)
        if len(written_pixels) != expected_bytes:
            message = (
                f"Krita stored {len(written_pixels)} bytes for the generated layer; "
                f"expected {expected_bytes}"
            )
            raise RuntimeError(message)

        # The PNG has been decoded as sRGB. Convert the populated paint layer
        # into the document's model, depth, and profile after the pixel write.
        if not node.setColorSpace(document.colorModel(), document.colorDepth(), document.colorProfile()):
            message = (
                "Krita could not convert the generated layer into the document "
                f"color space ({document.colorModel()}, {document.colorDepth()}, "
                f"{document.colorProfile()})"
            )
            raise RuntimeError(message)

        node.setVisible(True)
        document.setActiveNode(node)
        document.refreshProjection()
        document.setModified(True)

        if node.parentNode() != parent:
            message = "The generated layer moved unexpectedly during color conversion"
            raise RuntimeError(message)

        return node
    except Exception:
        parent = node.parentNode()
        if parent is not None:
            parent.removeChildNode(node)
            document.refreshProjection()
        raise
