from aiohttp import web

from server import PromptServer

from .constants import KRITA_INPUT_NODE_TYPES, KRITA_OUTPUT_NODE_TYPES
from .models import PrunedKritaWorkflow, UpdateKritaDocumentsRequest, UpdateWorkflowRequest, DocumentMappingResponse
from .krita_api import api


def define_routes():
    _define_krita_routes()
    _define_comfy_routes()


def _define_krita_routes():
    @PromptServer.instance.routes.put("/krita/{sid}/documents")
    async def update_documents(request):
        sid = request.match_info["sid"]
        unvalidated_update_request = await request.json()
        unvalidated_update_request.update({"sid": sid})
        try:
            update_request = UpdateKritaDocumentsRequest.model_validate(unvalidated_update_request)
            local_document_mapping = await api.update_documents(update_request.sid, update_request.documents)
            mapping_response = DocumentMappingResponse(mapping=local_document_mapping)
            return web.json_response(mapping_response.model_dump())
        except:
            return web.json_response(status=400)

    @PromptServer.instance.routes.get("/krita/{sid}/workflows")
    async def get_comfy_workflows(request):
        # TODO:
        # Return a list of workflows, one per document associated with the sid
        # It's one workflow per document
        return web.json_response(status=500, reason="Not implemented")


def _define_comfy_routes():
    @PromptServer.instance.routes.put("/krita/documents/{id}/workflow")
    async def update_workflow(request):
        document_id = request.match_info["id"]
        try:
            workflow_request = UpdateWorkflowRequest.model_validate(await request.json())
            name = workflow_request.name
            input_nodes = [node for node in workflow_request.workflow.nodes if node.type in KRITA_INPUT_NODE_TYPES]
            output_nodes = [node for node in workflow_request.workflow.nodes if node.type in KRITA_OUTPUT_NODE_TYPES]
            pruned_workflow = PrunedKritaWorkflow(name=name, inputs=input_nodes, outputs=output_nodes)
            await api.update_workflow(document_id, pruned_workflow)
        except:
            return web.json_response(status=400)
        return web.json_response()

    @PromptServer.instance.routes.get("/krita/documents")
    async def get_krita_documents(request):
        try:
            await api.prune_stale_sids_async()
            krita_documents = api.get_registered_documents()
            return web.json_response(krita_documents.model_dump())
        except:
            return web.json_response(status=400)
