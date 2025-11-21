import json

from .comfy_websocket import ComfyWebsocket
from .document_monitor import DocumentMonitor
from .models import DocumentMappingResponse, StatusRequest, UpdateDocumentsRequest, UpdateWorkflowsRequest


class ComfyKritaBridge:
    def __init__(self, comfy_ws: ComfyWebsocket, document_monitor: DocumentMonitor) -> None:
        self.comfy_ws = comfy_ws
        self.document_monitor = document_monitor
        self._define_commands()

    def _define_commands(self) -> None:
        @self.comfy_ws.handler("status")
        def status_statement(data: dict) -> None:
            status_request = StatusRequest.model_validate(data)
            self.status_statement(status_request)

        @self.comfy_ws.handler("krita::workflows::update")
        def update_workflows(data: dict) -> None:
            workflows_request = UpdateWorkflowsRequest.model_validate(data)
            self.update_workflows(workflows_request)

    def status_statement(self, status_request: StatusRequest) -> None:
        self.comfy_ws.sid = status_request.sid
        self.update_documents()

    def update_documents(self) -> None:
        if not self.comfy_ws.is_connected:
            return

        mappings = self.generate_document_name_mappings()

        if not self.document_monitor.test_mappings(mappings):
            mappings = self.generate_document_name_mappings()

        self.document_monitor.assign_name_mappings(mappings)
        self.request_workflows()

    def request_workflows(self) -> None:
        if self.comfy_ws.sid is None:
            message = "The sid is not defined"
            raise ValueError(message)

        data = self.comfy_ws.get(f"krita/{self.comfy_ws.sid}/workflows")

        # None is allowed, no workflows for our sid
        if json.loads(data) is None:
            return

        workflows_request = UpdateWorkflowsRequest.model_validate_json(data)
        self.update_workflows(workflows_request)

    def generate_document_name_mappings(self) -> dict[str, str]:
        if self.comfy_ws.sid is None:
            message = "The sid is not defined"
            raise ValueError(message)

        sid = self.comfy_ws.sid
        documents = [doc.name() for doc in self.document_monitor.get_opened_documents()]
        update_request = UpdateDocumentsRequest(documents=documents)
        response = self.comfy_ws.put(f"/krita/{sid}/documents", update_request.model_dump())
        return DocumentMappingResponse.model_validate_json(response).mapping

    def update_workflows(self, workflows_request: UpdateWorkflowsRequest) -> None:
        from . import ComfyUIExtension  # noqa: PLC0415

        for docker, window in ComfyUIExtension.get_comfyui_window_docker_pairs():
            active_document = window.activeView().document()

            found_document_id = None
            found_nodes = None

            for document_id, nodes in workflows_request.workflows.items():
                document = self.document_monitor.mapping.get(document_id, None)

                if document != active_document:
                    continue

                found_document_id = document_id
                found_nodes = nodes

            if found_document_id is None:
                return

            if found_nodes is None:
                return

            docker.update_title(workflows_request.name, found_document_id)
            docker.update_node_list(found_nodes, active_document)
