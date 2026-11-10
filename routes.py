from io import BytesIO
from zipfile import BadZipFile, ZipFile

from aiohttp import web
from aiohttp.web import Request, Response
from server import PromptServer

from .constants import KRITA_IO_NODE_TYPES, KRITA_OUTPUT_NODE_TYPES
from .krita_api import api
from .models import (
    DocumentMappingResponse,
    KritaNodeStateUpdate,
    LoadImageState,
    UpdateKritaDocumentsRequest,
    UpdateWorkflowsRequest,
)

MAX_LOAD_IMAGE_UPLOAD_BYTES = 65 * 1024 * 1024
MAX_LOAD_IMAGE_STATE_BYTES = 1024 * 1024
MAX_LOAD_IMAGE_PNG_BYTES = 64 * 1024 * 1024
LOAD_IMAGE_PACKAGE_MEMBERS = frozenset({"state.json", "composite.png"})


def define_routes() -> None:
    _define_krita_routes()
    _define_comfy_routes()


def _define_krita_routes() -> None:
    _define_document_routes()
    _define_node_state_routes()
    _define_input_image_routes()
    _define_image_transfer_routes()


def _define_document_routes() -> None:
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
                update_request.previous_mappings,
            )
            mapping_response = DocumentMappingResponse(mapping=local_document_mapping)
            return web.json_response(mapping_response.model_dump())
        except Exception:  # noqa: BLE001
            return web.json_response(status=400)

    @PromptServer.instance.routes.get("/krita/{sid}/workflows")
    async def get_krita_workflows(request: Request) -> Response:
        sid = request.match_info["sid"]
        try:
            krita_workflows = api.get_registered_workflows_by_sid(sid)
            return web.json_response(krita_workflows.model_dump() if krita_workflows is not None else None)
        except Exception:  # noqa: BLE001
            return web.json_response(status=400)


def _define_node_state_routes() -> None:
    @PromptServer.instance.routes.put("/krita/{sid}/nodes/state")
    async def update_node_state(request: Request) -> Response:
        sid = request.match_info["sid"]
        try:
            update = KritaNodeStateUpdate.model_validate(await request.json())
            await api.update_node_state(sid, update)
        except LookupError:
            return web.json_response(status=404)
        except Exception:  # noqa: BLE001
            return web.json_response(status=400)
        return web.json_response()

    @PromptServer.instance.routes.get("/krita/nodes/states")
    async def get_node_states(request: Request) -> Response:  # noqa: ARG001
        try:
            await api.prune_stale_sids_async()
            states = [state.model_dump() for state in api.get_node_states()]
            return web.json_response({"states": states})
        except Exception:  # noqa: BLE001
            return web.json_response(status=400)



def _define_input_image_routes() -> None:
    PromptServer.instance.routes.put("/krita/{sid}/nodes/load-image")(_upload_load_image_snapshot)


async def _upload_load_image_snapshot(request: Request) -> Response:
    sid = request.match_info["sid"]
    try:
        package_data = await _read_load_image_package(request)
        state, image_data = _parse_load_image_package(package_data)
        await api.store_load_image_snapshot(sid, state, image_data)
    except LoadImagePackageTooLargeError:
        return web.json_response(
            {"error": "The layer snapshot package is too large"},
            status=413,
        )
    except LookupError as error:
        return web.json_response({"error": str(error)}, status=404)
    except (BadZipFile, KeyError, ValueError) as error:
        return web.json_response({"error": str(error)}, status=400)
    except Exception:  # noqa: BLE001
        return web.json_response(
            {"error": "Could not store the Krita layer snapshot"},
            status=400,
        )
    return web.json_response()


class LoadImagePackageTooLargeError(ValueError):
    """Raised when the uploaded snapshot archive exceeds the configured limit."""


async def _read_load_image_package(request: Request) -> bytes:
    if request.content_length is not None and request.content_length > MAX_LOAD_IMAGE_UPLOAD_BYTES:
        raise LoadImagePackageTooLargeError

    package_buffer = bytearray()
    async for chunk in request.content.iter_chunked(1024 * 1024):
        if len(package_buffer) + len(chunk) > MAX_LOAD_IMAGE_UPLOAD_BYTES:
            raise LoadImagePackageTooLargeError
        package_buffer.extend(chunk)

    if not package_buffer:
        message = "The layer snapshot package is empty"
        raise ValueError(message)
    return bytes(package_buffer)

def _parse_load_image_package(package_data: bytes) -> tuple[LoadImageState, bytes]:
    with ZipFile(BytesIO(package_data)) as archive:
        infos = archive.infolist()
        names = {info.filename for info in infos}
        if len(infos) != len(LOAD_IMAGE_PACKAGE_MEMBERS) or names != LOAD_IMAGE_PACKAGE_MEMBERS:
            message = "The layer snapshot package is incomplete"
            raise ValueError(message)
        if archive.getinfo("state.json").file_size > MAX_LOAD_IMAGE_STATE_BYTES:
            message = "The layer snapshot state is too large"
            raise ValueError(message)
        if archive.getinfo("composite.png").file_size > MAX_LOAD_IMAGE_PNG_BYTES:
            message = "The layer snapshot image is too large"
            raise ValueError(message)

        state = LoadImageState.model_validate_json(archive.read("state.json"))
        image_data = archive.read("composite.png")
    return state, image_data

def _define_image_transfer_routes() -> None:
    @PromptServer.instance.routes.get("/krita/images/{transfer_id}")
    async def get_generated_image(request: Request) -> Response:
        transfer_id = request.match_info["transfer_id"]
        image_data = api.get_staged_image(transfer_id)
        if image_data is None:
            return web.Response(status=404)
        return web.Response(
            body=image_data,
            content_type="image/png",
            headers={"Cache-Control": "no-store"},
        )


def _define_comfy_routes() -> None:
    @PromptServer.instance.routes.put("/krita/documents/workflows")
    async def update_workflows(request: Request) -> Response:
        try:
            workflows_request = UpdateWorkflowsRequest.model_validate(
                await request.json(),
            )
            workflows = workflows_request.workflows

            for document_id, nodes in workflows.items():
                for node in nodes:
                    node.direction = "output" if node.type in KRITA_OUTPUT_NODE_TYPES else "input"

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
