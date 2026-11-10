# noqa: N999
from pathlib import Path
import secrets
from typing import override

from PIL import Image as PilImage
from comfy import model_management
from comfy_api.latest import ComfyExtension, io
from pydantic import ValidationError
from torch import Tensor
from torchvision.transforms.functional import to_pil_image

import folder_paths

from .constants import (
    DEFAULT_KRITA_LOAD_IMAGE_STATE,
    DEFAULT_KRITA_NODE_STATE,
    KRITA_DOCUMENT_DROPDOWN_LABEL,
    KRITA_LOAD_IMAGE_NODE_TYPE,
    KRITA_SAVE_IMAGE_NODE_TYPE,
    META_WIDGET_LABEL,
)
from .krita_api import api
from .load_image_helpers import decode_composited_png
from .models import LoadImageState, SaveImageState
from .routes import define_routes

WEB_DIRECTORY = "."
IMAGE_BATCH_DIMENSIONS = 4
IMAGE_DIMENSIONS = 3
SUPPORTED_IMAGE_CHANNEL_COUNTS = (1, 3, 4)
define_routes()


def _to_pil_images(image: Tensor) -> list[PilImage.Image]:
    if image.ndim == IMAGE_BATCH_DIMENSIONS:
        images = image
    elif image.ndim == IMAGE_DIMENSIONS:
        images = image.unsqueeze(0)
    else:
        message = f"Expected a 3D or 4D ComfyUI image tensor, received {image.ndim} dimensions"
        raise ValueError(message)

    result = []
    for item in images:
        image_tensor = item
        if image_tensor.shape[-1] in SUPPORTED_IMAGE_CHANNEL_COUNTS:
            image_tensor = image_tensor.permute(2, 0, 1)
        result.append(to_pil_image(image_tensor.detach().cpu()))
    return result


def _write_preview_image(image_data: bytes) -> dict[str, str]:
    filename = f"krita_{secrets.token_hex(12)}.png"
    filepath = Path(folder_paths.get_temp_directory()) / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("wb") as preview_file:
        preview_file.write(image_data)
    return {"filename": filename, "subfolder": "", "type": "temp"}


class KritaSaveImage(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id=KRITA_SAVE_IMAGE_NODE_TYPE,
            display_name="Save Image (as krita layer)",
            category="krita",
            is_output_node=True,
            inputs=[
                io.Image.Input(id="image", display_name="image"),
                io.Combo.Input(
                    id=KRITA_DOCUMENT_DROPDOWN_LABEL,
                    options=[],
                    display_name=KRITA_DOCUMENT_DROPDOWN_LABEL,
                    optional=True,
                    tooltip="Select a connected Krita document.",
                ),
                io.String.Input(
                    id=META_WIDGET_LABEL,
                    display_name=META_WIDGET_LABEL,
                    default=DEFAULT_KRITA_NODE_STATE,
                    optional=True,
                    tooltip="Internal Krita output-node state.",
                    extra_dict={"hidden": True},
                ),
            ],
        )

    @classmethod
    def validate_inputs(cls, **kwargs: object) -> bool | str:
        document_value = kwargs.get(KRITA_DOCUMENT_DROPDOWN_LABEL)
        if not isinstance(document_value, str) or not document_value:
            return "Select a connected Krita document before running this node."

        registered_documents = api.get_registered_documents().documents
        if document_value not in registered_documents:
            return f"The Krita document {document_value!r} is not currently connected."

        meta = kwargs.get(META_WIDGET_LABEL)
        if not isinstance(meta, str) or not meta:
            return "Krita output-node state has not synchronized yet."

        try:
            state = SaveImageState.model_validate_json(meta)
        except ValidationError:
            return "Krita output-node metadata is invalid; reconnect Krita to synchronize it."

        if state.document_id != document_value:
            return "The selected Krita document does not match the synchronized output-node state."

        return True

    @classmethod
    def execute(
        cls,
        image: Tensor,
        **kwargs: dict | list | float | str | None,
    ) -> io.NodeOutput:  # type: ignore
        document_value = kwargs.get(KRITA_DOCUMENT_DROPDOWN_LABEL)
        if not isinstance(document_value, str) or not document_value:
            message = "Select a Krita document before running this output node"
            raise ValueError(message)

        meta = kwargs.get(META_WIDGET_LABEL)
        if not isinstance(meta, str) or not meta:
            message = "Krita output-node state has not synchronized yet; wait for the Krita connection"
            raise ValueError(message)

        images = _to_pil_images(image)
        batch_size = len(images)
        for index, pil_image in enumerate(images):
            api.create_layer(
                document_value,
                meta,
                pil_image,
                batch_index=index,
                batch_size=batch_size,
            )

        return io.NodeOutput()


class KritaLoadImage(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id=KRITA_LOAD_IMAGE_NODE_TYPE,
            display_name="Load Image (from krita layers)",
            category="krita",
            inputs=[
                io.Combo.Input(
                    id=KRITA_DOCUMENT_DROPDOWN_LABEL,
                    options=[],
                    display_name=KRITA_DOCUMENT_DROPDOWN_LABEL,
                    optional=True,
                    tooltip="Select the Krita document containing the selected layers.",
                ),
                io.String.Input(
                    id=META_WIDGET_LABEL,
                    display_name=META_WIDGET_LABEL,
                    default=DEFAULT_KRITA_LOAD_IMAGE_STATE,
                    optional=True,
                    tooltip="Internal Krita input-node state.",
                    extra_dict={"hidden": True},
                ),
            ],
            outputs=[
                io.Image.Output(id="layers", display_name="layers"),
                io.Mask.Output(id="mask", display_name="mask"),
            ],
        )

    @classmethod
    def validate_inputs(cls, **kwargs: object) -> bool | str:
        document_value = kwargs.get(KRITA_DOCUMENT_DROPDOWN_LABEL)
        meta = kwargs.get(META_WIDGET_LABEL)
        validation_checks = (
            (
                not isinstance(document_value, str) or not document_value,
                "Select a connected Krita document before running this node.",
            ),
            (
                document_value not in api.get_registered_documents().documents,
                f"The Krita document {document_value!r} is not currently connected.",
            ),
            (
                not isinstance(meta, str) or not meta,
                "Krita layer selection has not synchronized yet.",
            ),
        )
        for invalid, message in validation_checks:
            if invalid:
                return message

        try:
            state = LoadImageState.model_validate_json(meta)
        except ValidationError:
            return "Krita input-node metadata is invalid; reconnect Krita to synchronize it."

        state_checks = (
            (
                state.document_id != document_value,
                "The selected Krita document does not match the synchronized input-node state.",
            ),
            (
                not state.layer_ids or not state.snapshot_revision,
                "Select one or more layers in Krita and accept the selection.",
            ),
            (
                not api.has_load_image_snapshot(state),
                "The selected Krita layers have not been uploaded yet; reselect them in Krita.",
            ),
        )
        for invalid, message in state_checks:
            if invalid:
                return message
        return True

    @classmethod
    def execute(
        cls,
        **kwargs: dict | list | float | str | None,
    ) -> io.NodeOutput:  # type: ignore
        document_value = kwargs.get(KRITA_DOCUMENT_DROPDOWN_LABEL)
        meta = kwargs.get(META_WIDGET_LABEL)
        if not isinstance(document_value, str) or not isinstance(meta, str):
            message = "Select a Krita document and confirm a layer selection before running this node."
            raise TypeError(message)

        state = LoadImageState.model_validate_json(meta)
        if state.document_id != document_value:
            message = "The selected Krita document does not match the synchronized input-node state."
            raise ValueError(message)

        image_data = api.get_load_image_snapshot(state)
        if image_data is None:
            message = "The selected Krita layer snapshot is unavailable; reselect the layers in Krita."
            raise ValueError(message)

        layers, mask = decode_composited_png(
            image_data,
            device=model_management.intermediate_device(),
            dtype=model_management.intermediate_dtype(),
        )
        preview_info = _write_preview_image(image_data)
        return io.NodeOutput(layers, mask, ui={"images": [preview_info]})


class KritaExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            KritaSaveImage,
            KritaLoadImage,
        ]


async def comfy_entrypoint() -> ComfyExtension:
    return KritaExtension()
