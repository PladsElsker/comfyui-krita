from typing import TYPE_CHECKING, ClassVar

from krita import DockWidget, Document, Window

from comfyui.extension.layer_manager.persistent_manager import PersistentLayerManager
from comfyui.extension.models import Node

from .comfyui_node import ComfyUiNode
from .save_image_node import SaveImageNode

if TYPE_CHECKING:
    from comfyui.extension.layer_manager import LayerManager


class NodeFactory:
    LayerManager: ClassVar[type["LayerManager"]] = PersistentLayerManager

    @classmethod
    def create(cls, docker: DockWidget, node: Node, window: Window, document: Document) -> ComfyUiNode:
        match node.type:
            case SaveImageNode.type:
                layer_manager = cls.LayerManager.get_by_window_and_document(window, document)
                return SaveImageNode(docker, node, layer_manager)

        message = f"Unknown node type {node.type}"
        raise ValueError(message)
