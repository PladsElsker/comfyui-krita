
from krita import DockWidget, Document, Window

from comfyui.extension.models import Node

from .comfyui_node import ComfyUiNode
from .save_image_node import SaveImageNode

class NodeFactory:
    @classmethod
    def create(cls, docker: DockWidget, node: Node, window: Window, document: Document, document_id: str) -> ComfyUiNode:
        match node.type:
            case SaveImageNode.type:
                return SaveImageNode(docker, node, window, document, document_id)

        message = f"Unknown node type {node.type}"
        raise ValueError(message)
