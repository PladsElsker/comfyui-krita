from .models import StatusRequest, UpdateKritaDocumentsRequest, UpdateKritaWorkflowRequest
from .comfy_websocket import ComfyWebsocket
from .document_monitor import DocumentMonitor
from .models import DocumentMappingResponse
from typing import Dict

from PyQt5.QtCore import qDebug


class ComfyKritaBridge:
    def __init__(self, comfy_ws: ComfyWebsocket, document_monitor: DocumentMonitor):
        self.comfy_ws = comfy_ws
        self.document_monitor = document_monitor
        self._define_commands()
    
    def _define_commands(self):
        @self.comfy_ws.handler("status")
        def status_statement(data: dict):
            status_request = StatusRequest.model_validate(data)
            return self.status_statement(status_request)

        @self.comfy_ws.handler("krita::workflow::update")
        def update_workflow(data: dict):
            workflow_request = UpdateKritaWorkflowRequest.model_validate(data)
            return self.update_workflow(workflow_request)

    def status_statement(self, status_request: StatusRequest):
        self.comfy_ws.sid = status_request.sid
        self.update_documents()

    def update_documents(self):
        if not self.comfy_ws.is_connected:
            return

        try:
            mappings = self.generate_document_name_mappings()

            if not self.document_monitor.test_mappings(mappings):
                mappings = self.generate_document_name_mappings()

            self.document_monitor.assign_name_mappings(mappings)
            qDebug(f"Received {mappings}")
        except Exception as exception:
            qDebug(str(exception))

    def generate_document_name_mappings(self) -> Dict[str, str]:
        if self.comfy_ws.sid is None:
            raise ValueError("The sid is not defined")

        sid = self.comfy_ws.sid
        documents = [doc.name() for doc in self.document_monitor.get_last_docs()]
        update_request = UpdateKritaDocumentsRequest(documents=documents)
        response = self.comfy_ws.put(f"/krita/{sid}/documents", update_request.model_dump())
        return DocumentMappingResponse.model_validate_json(response).mapping

    def update_workflow(self, workflow_request: UpdateKritaWorkflowRequest):
        from . import ComfyUIExtension

        try:
            for docker in ComfyUIExtension.get_comfyui_dockers():
                document = self.document_monitor.mapping.get(workflow_request.id, None)

                if document is None:
                    raise ValueError(f"Unable to find document referenced by id {workflow_request.id}.")
                
                docker.update_workflow(workflow_request.workflow)

            qDebug(workflow_request.model_dump_json())
        except Exception as exception:
            qDebug(str(exception))
