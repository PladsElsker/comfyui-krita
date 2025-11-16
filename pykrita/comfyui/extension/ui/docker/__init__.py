from krita import DockWidget
from PyQt5.QtWidgets import QVBoxLayout,  QWidget

from ...models import PrunedKritaWorkflow

from .workflow_header import WorkflowHeader
from .node_list_widget import NodeListWidget


COMFYUI_DOCKER_OBJECT_NAME = "comfyui_docker"


class ComfyUIDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ComfyUI")

        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.setWidget(self.container)

        self.workflow_header = WorkflowHeader()
        self.main_layout.addWidget(self.workflow_header)

        self.node_list = NodeListWidget()
        self.main_layout.addWidget(self.node_list)

    def is_assigned_to(self, document_id):
        # TODO: 
        # Handle multi docker interactions. 

        return True

    def update_workflow(self, workflow: PrunedKritaWorkflow):
        # TODO: 
        # Handle multi docker interactions. 

        self.workflow_header.set_workflow_name(workflow.name)
        self.node_list.rebuild(workflow.inputs, workflow.outputs)

    def canvasChanged(self, canvas):
        pass

