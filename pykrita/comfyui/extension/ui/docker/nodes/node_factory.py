from ....layers_manager import PersistentLayerManager
from ....models import Node
from .comfyui_node import ComfyUiNode
from .save_image_node import SaveImageNode
from .test_node import TestNode


class NodeFactory:
    @staticmethod
    def create(node: Node, layers_manager: PersistentLayerManager) -> ComfyUiNode:
        match node.type:
            case SaveImageNode.type:
                return TestNode(node, layers_manager)

        message = f"Unknown node type {node.type}"
        raise ValueError(message)
