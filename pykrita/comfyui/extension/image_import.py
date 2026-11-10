from krita import Document, Node
from PyQt5.QtCore import qCritical, qInfo, qWarning
from PyQt5.QtGui import QImage

from comfyui.extension.layer_tree.utils import LayerUtils
from comfyui.extension.models import FlatLayerToken

_SRGB_PROFILES = ("sRGB-elle-V2-srgbtrc.icc", "sRGB built-in")


def _set_srgb_color_space(node: Node) -> bool:
    return any(node.setColorSpace("RGBA", "U8", profile) for profile in _SRGB_PROFILES)


def _decode_png(image_data: bytes) -> tuple[int, int, bytes]:
    qWarning(f"[ComfyUI Krita Image] PNG decode starting: bytes={len(image_data)}, " f"signature={image_data[:8].hex()}")
    image = QImage.fromData(image_data, "PNG")
    if image.isNull():
        qCritical("[ComfyUI Krita Image] PNG DECODE FAILED: QImage.fromData returned a null image")
        message = "The generated image payload is not a valid PNG"
        raise ValueError(message)

    # Krita's paint-device buffer uses QImage's native ARGB32 byte layout.
    # This matches the conversion used by established Krita integrations.
    qWarning(
        f"[ComfyUI Krita Image] PNG decoded: width={image.width()}, height={image.height()}, "
        f"original_format={image.format()}, bytes_per_line={image.bytesPerLine()}"
    )
    image = image.convertToFormat(QImage.Format_ARGB32)
    width = image.width()
    height = image.height()
    pixel_data = bytes(image.bits().asstring(image.byteCount()))
    expected_bytes = width * height * 4
    qWarning(
        f"[ComfyUI Krita Image] Pixel buffer prepared: format=ARGB32, width={width}, "
        f"height={height}, byte_count={len(pixel_data)}, expected={expected_bytes}, "
        f"contains_nonzero_data={any(pixel_data)}"
    )
    if len(pixel_data) != expected_bytes:
        qCritical(f"[ComfyUI Krita Image] PIXEL BUFFER SIZE MISMATCH: actual={len(pixel_data)}, " f"expected={expected_bytes}")
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
    qWarning(
        f"[ComfyUI Krita Image] Creating paint layer: document={document.name()!r}, "
        f"layer_name={layer_name!r}, size={width}x{height}, "
        f"document_color={document.colorModel()}/{document.colorDepth()}/{document.colorProfile()}"
    )
    node = document.createNode(layer_name, "paintlayer")
    if node is None:
        qCritical("[ComfyUI Krita Image] LAYER CREATION FAILED: Document.createNode returned None")
        message = "Krita could not create a paint layer for the generated image"
        raise RuntimeError(message)
    qWarning(f"[ComfyUI Krita Image] Paint layer created: name={node.name()!r}, type={node.type()}")

    source_color_space = _set_srgb_color_space(node)
    qWarning(
        f"[ComfyUI Krita Image] Source color-space setup: success={source_color_space}, "
        f"result={node.colorModel()}/{node.colorDepth()}/{node.colorProfile()}"
    )
    if not source_color_space:
        qCritical("[ComfyUI Krita Image] COLOR-SPACE SETUP FAILED: no configured sRGB profile was accepted")
        message = "Krita could not prepare an sRGB color space for the generated layer"
        raise RuntimeError(message)

    pixel_write_result = node.setPixelData(pixel_data, 0, 0, width, height)
    qWarning(
        f"[ComfyUI Krita Image] setPixelData returned {pixel_write_result!r} "
        f"(type={type(pixel_write_result).__name__}); "
        f"layer color={node.colorModel()}/{node.colorDepth()}/{node.colorProfile()}"
    )
    # Krita 5.2.x shipped a SIP declaration that exposed this bool-returning
    # C++ method as void, so Python receives None even when the write succeeds.
    # Only an explicit False is a failed write; None must be verified by readback.
    if pixel_write_result is False:
        qCritical("[ComfyUI Krita Image] PIXEL WRITE FAILED: Krita explicitly returned False")
        message = "Krita rejected the generated image pixel buffer"
        raise RuntimeError(message)

    written_pixels = bytes(node.pixelData(0, 0, width, height))
    expected_bytes = width * height * 4
    qWarning(
        f"[ComfyUI Krita Image] Pixel readback: byte_count={len(written_pixels)}, "
        f"expected={expected_bytes}, matches_input={written_pixels == pixel_data}, "
        f"contains_nonzero_data={any(written_pixels)}"
    )
    if len(written_pixels) != expected_bytes:
        qCritical(f"[ComfyUI Krita Image] PIXEL READBACK FAILED: actual={len(written_pixels)}, " f"expected={expected_bytes}")
        message = f"Krita stored {len(written_pixels)} bytes for the generated layer; expected {expected_bytes}"
        raise RuntimeError(message)

    if written_pixels != pixel_data:
        first_mismatch = next(
            (index for index, (actual, expected) in enumerate(zip(written_pixels, pixel_data, strict=True)) if actual != expected),
            None,
        )
        qCritical(
            f"[ComfyUI Krita Image] PIXEL CONTENT MISMATCH: first_different_byte={first_mismatch}, "
            f"actual_length={len(written_pixels)}, expected_length={len(pixel_data)}"
        )
        message = "Krita pixel readback does not match the generated PNG pixel buffer"
        raise RuntimeError(message)

    qWarning("[ComfyUI Krita Image] Pixel write verified byte-for-byte")

    return node


def insert_png_image(
    document: Document,
    image_data: bytes,
    path: list[FlatLayerToken],
    layer_name: str,
) -> Node:
    qWarning(
        f"[ComfyUI Krita Image] Import routine entered: document={document.name()!r}, "
        f"document_id_is_resolved=True, path={[(token.type, str(token.quuid) if token.quuid is not None else None) for token in path]}"
    )
    width, height, pixel_data = _decode_png(image_data)
    node = _create_populated_layer(document, layer_name, width, height, pixel_data)

    qWarning(f"[ComfyUI Krita Image] Target insertion resolution starting: layer={node.name()!r}")
    relative_path = LayerUtils.rebase_path(document, path)
    if relative_path is None:
        qCritical("[ComfyUI Krita Image] TARGET RESOLUTION FAILED: rebase_path returned None")
        message = "The rebased output insertion parent no longer exists"
        raise ValueError(message)
    qWarning(
        f"[ComfyUI Krita Image] Target insertion resolved: parent={relative_path.parent.name()!r} "
        f"({relative_path.parent.type()}), sibling="
        f"{relative_path.sibling.name() if relative_path.sibling is not None else None!r}"
    )

    # Keep the existing target-resolution/rebasing implementation intact.
    LayerUtils.insert_node(document, node, path)
    parent = node.parentNode()
    if parent is None:
        qCritical("[ComfyUI Krita Image] NODE ATTACH FAILED: node.parentNode() is None after insert_node")
        message = "Krita did not attach the generated layer to the document"
        raise RuntimeError(message)
    qWarning(
        f"[ComfyUI Krita Image] Node attached: actual_parent={parent.name()!r} ({parent.type()}), "
        f"child_names={[child.name() for child in parent.childNodes()]}"
    )

    qWarning(
        f"[ComfyUI Krita Image] Document color conversion starting: "
        f"source={node.colorModel()}/{node.colorDepth()}/{node.colorProfile()}, "
        f"target={document.colorModel()}/{document.colorDepth()}/{document.colorProfile()}"
    )
    color_conversion = node.setColorSpace(document.colorModel(), document.colorDepth(), document.colorProfile())
    qWarning(
        f"[ComfyUI Krita Image] Document color conversion result={color_conversion}, "
        f"result_color={node.colorModel()}/{node.colorDepth()}/{node.colorProfile()}"
    )
    if not color_conversion:
        qCritical("[ComfyUI Krita Image] DOCUMENT COLOR CONVERSION FAILED")
        message = (
            "Krita could not convert the generated layer into the document color space "
            f"({document.colorModel()}, {document.colorDepth()}, {document.colorProfile()})"
        )
        raise RuntimeError(message)

    node.setVisible(True)
    qWarning(f"[ComfyUI Krita Image] Layer visibility after setVisible(True): {node.visible()}")
    document.setActiveNode(node)
    active_node = document.activeNode()
    qWarning(f"[ComfyUI Krita Image] Active layer after insertion: " f"{active_node.name() if active_node is not None else None!r}")
    document.refreshProjection()
    document.setModified(True)

    final_parent = node.parentNode()
    if final_parent is None:
        qCritical("[ComfyUI Krita Image] FINAL VERIFICATION FAILED: generated layer has no parent")
        message = "The generated layer became detached during color conversion"
        raise RuntimeError(message)

    qWarning(
        f"[ComfyUI Krita Image] Import routine complete: layer={node.name()!r}, "
        f"parent={final_parent.name()!r}, visible={node.visible()}, "
        f"pixel_size={width}x{height}, top_level_layers={[item.name() for item in document.topLevelNodes()]}"
    )
    return node
