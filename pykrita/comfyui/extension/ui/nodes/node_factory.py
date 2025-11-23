from comfyui.extension.layer_manager import LayerManager
from comfyui.extension.models import Node

from .comfyui_node import ComfyUiNode
from .save_image_node import SaveImageNode


class NodeFactory:
    @staticmethod
    def create(node: Node, layer_manager: LayerManager) -> ComfyUiNode:
        match node.type:
            case SaveImageNode.type:
                return SaveImageNode(node, layer_manager)

        message = f"Unknown node type {node.type}"
        raise ValueError(message)
