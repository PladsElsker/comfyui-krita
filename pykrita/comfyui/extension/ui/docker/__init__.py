from krita import DockWidget, Document
from PyQt5.QtWidgets import QVBoxLayout,  QWidget

from ...models import Node

from .workflow_header import WorkflowHeader
from .node_list_widget import NodeListWidget


COMFYUI_DOCKER_OBJECT_NAME = "comfyui_docker"


class ComfyUIDocker(DockWidget):
    def __init__(self):
        super().__init__()

        self._active_document = None
        self._workflows: dict[int, list[Node]] = {}
        self._registered_documents: list[Document] = []

        self.setWindowTitle("ComfyUI")

        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.setWidget(self.container)

        self.workflow_header = WorkflowHeader()
        self.main_layout.addWidget(self.workflow_header)

        self.node_list = NodeListWidget()
        self.main_layout.addWidget(self.node_list)

    def update_title(self, name: str):
        self.workflow_header.set_workflow_name(name)

    def update_node_list(self, document: Document, nodes: list[Node]):
        document_index = -1
        if document not in self._registered_documents:
            self._registered_documents.append(document)
            document_index = len(self._registered_documents) - 1
        else:
            document_index = self._registered_documents.index(document)

        self._workflows[document_index] = nodes
        self.set_active_document(self._active_document)

    def set_active_document(self, document: Document | None):
        self._active_document = document

        if document is None:
            return

        if document not in self._registered_documents:
            return

        document_index = self._registered_documents.index(document)
        nodes = self._workflows[document_index]
        self.node_list.rebuild(nodes)

    def canvasChanged(self, canvas):
        pass

