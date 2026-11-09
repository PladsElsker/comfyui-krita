# noqa: N999
from typing import override

from comfy_api.latest import ComfyExtension, io
from pydantic import ValidationError
from torch import Tensor
from torchvision.transforms.functional import to_pil_image

from .constants import (
    DEFAULT_KRITA_NODE_STATE,
    KRITA_DOCUMENT_DROPDOWN_LABEL,
    KRITA_SAVE_IMAGE_NODE_TYPE,
    META_WIDGET_LABEL,
)
from .krita_api import api
from .models import SaveImageState
from .routes import define_routes

WEB_DIRECTORY = "."
IMAGE_BATCH_DIMENSIONS = 4
IMAGE_DIMENSIONS = 3
SUPPORTED_IMAGE_CHANNEL_COUNTS = (1, 3, 4)
define_routes()


def _to_pil_images(image: Tensor) -> list:
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
                ),
            ],
        )

    @classmethod
    def validate_inputs(
        cls,
        image: Tensor,
        **kwargs: dict | list | float | str | None,
    ) -> bool | str:
        # The dropdown values are supplied by the connected Krita session at
        # runtime, so the schema's empty options list cannot validate them.
        # ComfyUI's custom validator replaces the static Combo membership check;
        # validate every value that this node relies on here instead.
        if not isinstance(image, Tensor):
            return "The Save Image node requires a ComfyUI image tensor."

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
    def execute(cls, image: Tensor, **kwargs: dict | list | float | str | None) -> io.NodeOutput:  # type: ignore
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
            api.create_layer(document_value, meta, pil_image, batch_index=index, batch_size=batch_size)

        return io.NodeOutput()


class KritaExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            KritaSaveImage,
        ]


async def comfy_entrypoint() -> ComfyExtension:
    return KritaExtension()
