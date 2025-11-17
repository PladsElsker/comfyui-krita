import inspect
import re
from collections.abc import Callable

from PIL.Image import Image
from server import PromptServer

from .models import KritaDocuments, UpdateWorkflowsRequest

STALE_SIDS_PRUNING_REFRESH_RATE = 3


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

    def create_layer(self, document_id: str, meta: dict, image: Image) -> None:
        pass

    @prune_sids
    async def update_documents(self, sid: str, documents: list[str]) -> dict[str, str]:
        self.registered_documents.setdefault(sid, set())
        self.registered_documents[sid].clear()

        document_mapping = {}

        for document_id in documents:
            unique_document_id = _ensure_unique_id(
                document_id,
                self.get_registered_documents().documents,
            )
            document_mapping[unique_document_id] = document_id
            self.registered_documents[sid].add(unique_document_id)

        krita_documents = self.get_registered_documents().model_dump()
        await PromptServer.instance.send("krita::documents::update", krita_documents)

        return document_mapping

    @prune_sids
    async def update_workflows(self, workflows_request: UpdateWorkflowsRequest) -> None:
        sid_map = self._split_update_workflows_request_per_sids(workflows_request)

        for sid, request in sid_map.items():
            await PromptServer.instance.send(
                "krita::workflows::update",
                request.model_dump(),
                sid,
            )

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

    def _prune_stale_sids(self) -> None:
        PromptServer.instance.loop.create_task(self.prune_stale_sids_async())

    async def _unregister_documents_by_sid_async(self, sid: str) -> None:
        if sid in self.registered_documents:
            del self.registered_documents[sid]

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
