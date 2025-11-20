from krita import Canvas, DockWidget, Document
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ...models import Node
from .node_list import NodeListWidget
from .workflow_header import WorkflowHeader

COMFYUI_DOCKER_OBJECT_NAME = "comfyui_docker"


class ComfyUIDocker(DockWidget):
    def __init__(self) -> None:
        super().__init__()

        self._active_document = None
        self._workflows: dict[int, list[Node]] = {}
        self._registered_documents: list[Document] = []

        self.setWindowTitle("ComfyUI")

        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.setWidget(self.container)

        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.workflow_header = WorkflowHeader()
        self.main_layout.addWidget(self.workflow_header)

        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.separator_container = QWidget()
        self.separator_layout = QHBoxLayout(self.separator_container)
        self.separator_layout.setContentsMargins(4, 0, 4, 0)
        self.separator_layout.addWidget(self.separator)
        self.separator_container.setFixedHeight(2)
        self.main_layout.addWidget(self.separator_container)

        self.node_list = NodeListWidget()
        self.main_layout.addWidget(self.node_list)

    def update_title(self, name: str) -> None:
        self.workflow_header.set_workflow_name(name)

    def update_document_id(self, document_id: str) -> None:
        self.workflow_header.set_document_name(document_id)

    def update_node_list(self, document: Document, nodes: list[Node]) -> None:
        document_index = -1
        if document not in self._registered_documents:
            self._registered_documents.append(document)
            document_index = len(self._registered_documents) - 1
        else:
            document_index = self._registered_documents.index(document)

        self._workflows[document_index] = nodes
        self.set_active_document(self._active_document)

    def set_active_document(self, document: Document | None) -> None:
        self._active_document = document

        if document is None:
            return

        if document not in self._registered_documents:
            return

        document_index = self._registered_documents.index(document)
        nodes = self._workflows[document_index]
        self.node_list.rebuild(nodes)

    def canvasChanged(self, canvas: Canvas) -> None:  # noqa: N802
        pass
