from ....layers_manager import PersistentLayerManager
from ....models import Node
from .comfyui_node import ComfyUiNode
from .save_image_node import SaveImageNode


class NodeFactory:
    @staticmethod
    def create(node: Node, layers_manager: PersistentLayerManager) -> ComfyUiNode:
        match node.type:
            case SaveImageNode.type:
                return SaveImageNode(node, layers_manager)

        message = f"Unknown node type {node.type}"
        raise ValueError(message)
