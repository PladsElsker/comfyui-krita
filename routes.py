from aiohttp import web
from aiohttp.web import Request, Response
from server import PromptServer

from .constants import KRITA_IO_NODE_TYPES
from .krita_api import api
from .models import (
    DocumentMappingResponse,
    UpdateKritaDocumentsRequest,
    UpdateWorkflowsRequest,
)


def define_routes() -> None:
    _define_krita_routes()
    _define_comfy_routes()


def _define_krita_routes() -> None:
    @PromptServer.instance.routes.put("/krita/{sid}/documents")
    async def update_documents(request: Request) -> Response:
        sid = request.match_info["sid"]
        unvalidated_update_request = await request.json()
        unvalidated_update_request.update({"sid": sid})
        try:
            update_request = UpdateKritaDocumentsRequest.model_validate(
                unvalidated_update_request,
            )
            local_document_mapping = await api.update_documents(
                update_request.sid,
                update_request.documents,
            )
            mapping_response = DocumentMappingResponse(mapping=local_document_mapping)
            return web.json_response(mapping_response.model_dump())
        except Exception:  # noqa: BLE001
            return web.json_response(status=400)

    @PromptServer.instance.routes.get("/krita/{sid}/workflows")
    async def get_krita_workflows(request: Request) -> Response:  # noqa: ARG001
        sid = request.match_info["sid"]
        try:
            krita_workflows = api.get_registered_workflows_by_sid(sid)
            return web.json_response(krita_workflows.model_dump() if krita_workflows is not None else None)
        except Exception:  # noqa: BLE001
            return web.json_response(status=400)


def _define_comfy_routes() -> None:
    @PromptServer.instance.routes.put("/krita/documents/workflows")
    async def update_workflows(request: Request) -> Response:
        try:
            workflows_request = UpdateWorkflowsRequest.model_validate(
                await request.json(),
            )
            workflows = workflows_request.workflows

            for document_id, nodes in workflows.items():
                workflows[document_id] = [node for node in nodes if node.type in KRITA_IO_NODE_TYPES]

            await api.update_workflows(workflows_request)
        except Exception:  # noqa: BLE001
            return web.json_response(status=400)
        return web.json_response()

    @PromptServer.instance.routes.get("/krita/documents")
    async def get_krita_documents(request: Request) -> Response:  # noqa: ARG001
        try:
            await api.prune_stale_sids_async()
            krita_documents = api.get_registered_documents()
            return web.json_response(krita_documents.model_dump())
        except Exception:  # noqa: BLE001
            return web.json_response(status=400)
