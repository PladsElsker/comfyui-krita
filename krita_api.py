import inspect
import io
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from PIL.Image import Image
from server import PromptServer

from .models import (
    KritaDocuments,
    KritaNodeStateUpdate,
    LayerCreateNotification,
    SaveImageState,
    UpdateWorkflowsRequest,
)

STALE_SIDS_PRUNING_REFRESH_RATE = 3
STAGED_IMAGE_TTL_SECONDS = 180
MAX_STAGED_IMAGE_BYTES = 64 * 1024 * 1024
MAX_STAGED_TOTAL_BYTES = 256 * 1024 * 1024
MAX_STAGED_IMAGES = 128


@dataclass
class StagedImage:
    sid: str
    data: bytes
    expires_at: float


def prune_sids(f: Callable) -> Callable:
    if inspect.iscoroutinefunction(f):

        async def async_wrapper(self: "KritaApi", *args: tuple, **kwargs: dict) -> None:
            await self.prune_stale_sids_async()
            return await f(self, *args, **kwargs)

        return async_wrapper

    def wrapper(self: "KritaApi", *args: tuple, **kwargs: dict) -> None:
        self._prune_stale_sids()

        return f(self, *args, **kwargs)

    return wrapper


class KritaApi:
    def __init__(self) -> None:
        self.registered_documents: dict[str, set[str]] = {}
        self.document_mappings: dict[str, dict[str, str]] = {}
        self.node_states: dict[str, dict[tuple[str, int, str], SaveImageState]] = {}
        self._staged_images: dict[str, StagedImage] = {}
        self._last_workflows_request: UpdateWorkflowsRequest = UpdateWorkflowsRequest.default()

    def create_layer(
        self,
        document_id: str,
        meta: str | dict,
        image: Image,
        batch_index: int = 0,
        batch_size: int = 1,
    ) -> str:
        state = SaveImageState.model_validate_json(meta) if isinstance(meta, str) else SaveImageState.model_validate(meta)
        if state.document_id != document_id:
            message = "The Save Image node metadata does not match its selected Krita document"
            raise ValueError(message)

        sid = self._document_id_to_sid(document_id)
        if sid is None or sid not in PromptServer.instance.sockets:
            message = f"Krita document {document_id!r} is not connected"
            raise LookupError(message)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_data = buffer.getvalue()
        if len(image_data) > MAX_STAGED_IMAGE_BYTES:
            message = f"Generated PNG exceeds the {MAX_STAGED_IMAGE_BYTES}-byte transfer limit"
            raise ValueError(message)

        if len(image_data) > MAX_STAGED_TOTAL_BYTES:
            message = f"Generated PNG exceeds the {MAX_STAGED_TOTAL_BYTES}-byte staging budget"
            raise ValueError(message)

        self._prune_staged_images()
        while self._staged_images and (
            len(self._staged_images) >= MAX_STAGED_IMAGES
            or sum(len(staged.data) for staged in self._staged_images.values()) + len(image_data) > MAX_STAGED_TOTAL_BYTES
        ):
            oldest_transfer = min(self._staged_images, key=lambda key: self._staged_images[key].expires_at)
            self._staged_images.pop(oldest_transfer, None)

        transfer_id = secrets.token_urlsafe(24)
        self._staged_images[transfer_id] = StagedImage(
            sid=sid,
            data=image_data,
            expires_at=time.monotonic() + STAGED_IMAGE_TTL_SECONDS,
        )

        notification = LayerCreateNotification(
            transfer_id=transfer_id,
            state=state,
            batch_index=batch_index,
            batch_size=batch_size,
        )
        loop = PromptServer.instance.loop
        loop.call_soon_threadsafe(
            lambda: loop.create_task(self._send_layer_notification(sid, notification)),
        )
        return transfer_id

    async def _send_layer_notification(self, sid: str, notification: LayerCreateNotification) -> None:
        if sid not in PromptServer.instance.sockets:
            self._staged_images.pop(notification.transfer_id, None)
            return

        await PromptServer.instance.send(
            "krita::layers::create",
            notification.model_dump(),
            sid,
        )

    def get_staged_image(self, sid: str, transfer_id: str) -> bytes | None:
        self._prune_staged_images()
        staged = self._staged_images.get(transfer_id)
        if staged is None or staged.sid != sid:
            return None

        self._staged_images.pop(transfer_id, None)
        return staged.data

    def _prune_staged_images(self) -> None:
        now = time.monotonic()
        expired = [transfer_id for transfer_id, staged in self._staged_images.items() if staged.expires_at <= now]
        for transfer_id in expired:
            self._staged_images.pop(transfer_id, None)

    @prune_sids
    async def update_documents(
        self,
        sid: str,
        documents: list[str],
        previous_mappings: dict[str, str] | None = None,
    ) -> dict[str, str]:
        # Reuse prior IDs for documents that remain open so node-state keys
        # survive document-list refreshes. IDs used by other sessions stay reserved.
        occupied_ids = {
            document_id
            for registered_sid, registered_ids in self.registered_documents.items()
            if registered_sid != sid
            for document_id in registered_ids
        }
        previous_mappings = previous_mappings or self.document_mappings.get(sid, {})
        document_mapping: dict[str, str] = {}

        for document_name in documents:
            previous_id = next(
                (
                    candidate_id
                    for candidate_id, previous_name in previous_mappings.items()
                    if previous_name == document_name
                    and candidate_id not in occupied_ids
                    and candidate_id not in document_mapping
                ),
                None,
            )
            unique_document_id = previous_id or _ensure_unique_id(
                document_name,
                list(occupied_ids | set(document_mapping)),
            )
            document_mapping[unique_document_id] = document_name

        self.registered_documents[sid] = set(document_mapping)
        self.document_mappings[sid] = dict(document_mapping)

        registered_ids = set(document_mapping)
        sid_states = self.node_states.setdefault(sid, {})
        removed_keys = [key for key, state in sid_states.items() if state.document_id not in registered_ids]
        for key in removed_keys:
            state = sid_states.pop(key)
            await self._broadcast_deleted_node_state(state)

        krita_documents = self.get_registered_documents().model_dump()
        await PromptServer.instance.send("krita::documents::update", krita_documents)

        return document_mapping

    @prune_sids
    async def update_node_state(self, sid: str, update: KritaNodeStateUpdate) -> None:
        if sid not in self.registered_documents:
            message = "The Krita websocket session is not registered"
            raise LookupError(message)

        sid_states = self.node_states.setdefault(sid, {})
        if update.deleted:
            if update.document_id is None or update.id is None or update.type is None:
                message = "A deleted node-state update requires document_id, id, and type"
                raise ValueError(message)
            if update.document_id not in self.registered_documents[sid]:
                message = "The deleted node state does not belong to this Krita session"
                raise ValueError(message)

            sid_states.pop((update.document_id, update.id, update.type), None)
            await PromptServer.instance.send(
                "krita::nodes::update",
                {
                    "deleted": True,
                    "document_id": update.document_id,
                    "id": update.id,
                    "type": update.type,
                },
            )
            return

        state = update.state
        if state is None:
            message = "A node-state update requires state unless deleted is true"
            raise ValueError(message)
        if state.document_id not in self.registered_documents[sid]:
            message = "The node state does not belong to this Krita session"
            raise ValueError(message)

        key = (state.document_id, state.id, state.type)
        sid_states[key] = state
        await PromptServer.instance.send(
            "krita::nodes::update",
            {"deleted": False, "state": state.model_dump()},
        )

    def get_node_states(self) -> list[SaveImageState]:
        return [
            state
            for sid_states in self.node_states.values()
            for state in sid_states.values()
        ]

    @prune_sids
    async def update_workflows(self, workflows_request: UpdateWorkflowsRequest) -> None:
        self._last_workflows_request = workflows_request
        sid_map = self._split_update_workflows_request_per_sids(self._last_workflows_request)

        for sid, request in sid_map.items():
            await PromptServer.instance.send(
                "krita::workflows::update",
                request.model_dump(),
                sid,
            )

    @prune_sids
    def get_registered_workflows_by_sid(self, sid: str) -> UpdateWorkflowsRequest | None:
        return self._split_update_workflows_request_per_sids(self._last_workflows_request).get(sid, None)

    def get_registered_documents(self) -> KritaDocuments:
        return KritaDocuments(
            documents=sorted(
                [document_id for document_set in self.registered_documents.values() for document_id in document_set],
            ),
        )

    async def prune_stale_sids_async(self) -> None:
        has_changed = False

        for sid in list(self.registered_documents.keys()):
            if sid not in PromptServer.instance.sockets:
                del self.registered_documents[sid]
                self.document_mappings.pop(sid, None)
                for state in self.node_states.pop(sid, {}).values():
                    await self._broadcast_deleted_node_state(state)
                has_changed = True

        if not has_changed:
            return

        krita_documents = self.get_registered_documents().model_dump()
        await PromptServer.instance.send("krita::documents::update", krita_documents)

    def _split_update_workflows_request_per_sids(
        self,
        workflows_request: UpdateWorkflowsRequest,
    ) -> dict[str, UpdateWorkflowsRequest]:
        sid_request_map: dict[str, UpdateWorkflowsRequest] = {}
        document_id_sid_map: dict[str, str] = {}

        for document_id in self._get_registered_document_ids():
            if document_id in document_id_sid_map:
                sid = document_id_sid_map[document_id]
            else:
                sid = self._document_id_to_sid(document_id)

                if sid is None:
                    continue  # Ignored, Krita client disconnected

                document_id_sid_map[document_id] = sid

            if sid not in sid_request_map:
                sid_request_map[sid] = UpdateWorkflowsRequest(
                    name=workflows_request.name,
                    workflows={},
                )

            sid_request_map[sid].workflows[document_id] = workflows_request.workflows.get(document_id, [])

        return sid_request_map

    async def _broadcast_deleted_node_state(self, state: SaveImageState) -> None:
        await PromptServer.instance.send(
            "krita::nodes::update",
            {
                "deleted": True,
                "document_id": state.document_id,
                "id": state.id,
                "type": state.type,
            },
        )

    def _prune_stale_sids(self) -> None:
        PromptServer.instance.loop.create_task(self.prune_stale_sids_async())

    async def _unregister_documents_by_sid_async(self, sid: str) -> None:
        if sid in self.registered_documents:
            del self.registered_documents[sid]
            self.document_mappings.pop(sid, None)
            for state in self.node_states.pop(sid, {}).values():
                await self._broadcast_deleted_node_state(state)

    def _document_id_to_sid(self, document_id: str) -> str | None:
        return next(
            (sid for sid, document_set in self.registered_documents.items() for d in document_set if d == document_id),
            None,
        )

    def _get_registered_document_ids(self) -> set[str]:
        return {document_id for document_set in self.registered_documents.values() for document_id in document_set}


def _ensure_unique_id(document_id: str, registered_documents: list[str]) -> str:
    converted_id = document_id

    if document_id in registered_documents:
        regex = rf"{re.escape(document_id)} \((\d+)\)"
        same_ids = [i for i in registered_documents if re.match(regex, i)]
        matches = [re.fullmatch(regex, i) for i in same_ids]
        used_deduplicate_ids = {int(m.group(1)) for m in matches if m is not None}
        next_deduplicate_id = len(used_deduplicate_ids) + 1

        for i in range(len(used_deduplicate_ids)):
            if i + 1 not in used_deduplicate_ids:
                next_deduplicate_id = i + 1
                break

        converted_id = f"{document_id} ({next_deduplicate_id})"

    return converted_id


api = KritaApi()
