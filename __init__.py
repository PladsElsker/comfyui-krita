# noqa: N999
from typing import Any, override

from comfy_api.latest import ComfyExtension, io
from torch import Tensor

from .constants import (
    KRITA_DOCUMENT_DROPDOWN_LABEL,
    KRITA_SAVE_IMAGE_NODE_TYPE,
    META_WIDGET_LABEL,
)
from .krita_api import api
from .routes import define_routes

WEB_DIRECTORY = "."


define_routes()


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
                    tooltip="Select a Krita document.",
                    lazy=True,
                ),
                io.Combo.Input(
                    id=META_WIDGET_LABEL,
                    options=[],
                    display_name=META_WIDGET_LABEL,
                    optional=True,
                    lazy=True,
                ),
            ],
        )

    @classmethod
    def execute(cls, image: Tensor, **kwargs: dict[str, Any]) -> io.NodeOutput:  # type: ignore
        document = kwargs[KRITA_DOCUMENT_DROPDOWN_LABEL]
        meta = kwargs[META_WIDGET_LABEL]

        api.create_layer(document, meta, image)

        return io.NodeOutput()


class KritaExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            KritaSaveImage,
        ]


async def comfy_entrypoint() -> ComfyExtension:
    return KritaExtension()
