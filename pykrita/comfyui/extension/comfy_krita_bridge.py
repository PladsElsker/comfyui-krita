from .models import StatusRequest, UpdateKritaDocumentsRequest, UpdateWorkflowsRequest
from .comfy_websocket import ComfyWebsocket
from .document_monitor import DocumentMonitor
from .models import DocumentMappingResponse
from typing import Dict


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

        @self.comfy_ws.handler("krita::workflows::update")
        def update_workflows(data: dict):
            workflows_request = UpdateWorkflowsRequest.model_validate(data)
            return self.update_workflows(workflows_request)

    def status_statement(self, status_request: StatusRequest):
        self.comfy_ws.sid = status_request.sid
        self.update_documents()

    def update_documents(self):
        if not self.comfy_ws.is_connected:
            return

        mappings = self.generate_document_name_mappings()

        if not self.document_monitor.test_mappings(mappings):
            mappings = self.generate_document_name_mappings()

        self.document_monitor.assign_name_mappings(mappings)

    def generate_document_name_mappings(self) -> Dict[str, str]:
        if self.comfy_ws.sid is None:
            raise ValueError("The sid is not defined")

        sid = self.comfy_ws.sid
        documents = [doc.name() for doc in self.document_monitor.get_opened_documents()]
        update_request = UpdateKritaDocumentsRequest(documents=documents)
        response = self.comfy_ws.put(f"/krita/{sid}/documents", update_request.model_dump())
        return DocumentMappingResponse.model_validate_json(response).mapping

    def update_workflows(self, workflows_request: UpdateWorkflowsRequest):
        from . import ComfyUIExtension

        for docker in ComfyUIExtension.get_comfyui_dockers():
            docker.update_title(workflows_request.name)

            for document_id, nodes in workflows_request.workflows.items():
                document = self.document_monitor.mapping.get(document_id, None)

                if document is None:
                    raise ValueError(f"Unable to find document referenced by id {document_id}.")

                docker.update_node_list(document, nodes)
