import re
import inspect
from typing import Dict

from server import PromptServer

from .models import KritaDocuments, UpdateKritaWorkflowRequest, UpdateWorkflowsRequest


STALE_SIDS_PRUNING_REFRESH_RATE = 3


def prune_sids(f):
    if inspect.iscoroutinefunction(f):
        async def async_wrapper(self: 'KritaApi', *args, **kwargs):
            await self.prune_stale_sids_async()
            return await f(self, *args, **kwargs)

        return async_wrapper
    else:
        def wrapper(self: 'KritaApi', *args, **kwargs):
            self._prune_stale_sids()

            return f(self, *args, **kwargs)

        return wrapper


class KritaApi:
    def __init__(self) -> None:
        self.registered_documents: dict[str, set[str]] = {}

    def create_layer(self, document_id, layer_path, image):
        pass

    @prune_sids
    async def update_documents(self, sid, documents) -> Dict[str, str]:
        self.registered_documents.setdefault(sid, set())
        self.registered_documents[sid].clear()

        document_mapping = {}

        for document_id in documents:
            unique_document_id = _ensure_unique_id(document_id, self.get_registered_documents().documents)
            document_mapping[unique_document_id] = document_id
            self.registered_documents[sid].add(unique_document_id)

        krita_documents = self.get_registered_documents().model_dump()
        await PromptServer.instance.send("krita::documents::update", krita_documents)

        return document_mapping

    @prune_sids
    async def update_workflows(self, workflows_request: UpdateWorkflowsRequest):
        sid_request_map: Dict[str, UpdateWorkflowsRequest] = {}
        document_id_sid_map: Dict[str, str] = {}

        for document_id, nodes in workflows_request.workflows.items():
            if document_id in document_id_sid_map:
                sid = document_id_sid_map[document_id]
            else:
                sid = self.document_id_to_sid(document_id)

                if sid is None:
                    continue # Ignored, Krita client disconnected

                document_id_sid_map[document_id] = sid

            if sid not in sid_request_map:
                sid_request_map[sid] = UpdateWorkflowsRequest(name=workflows_request.name, workflows={})
            
            sid_request_map[sid].workflows[document_id] = nodes

        for sid, request in sid_request_map.items():
            await PromptServer.instance.send("krita::workflows::update", request.model_dump(), sid)

    def get_registered_documents(self) -> KritaDocuments:
        return KritaDocuments(documents=sorted([
            document_id
            for document_set in self.registered_documents.values()
            for document_id in document_set
        ]))

    async def prune_stale_sids_async(self):
        has_changed = False

        for sid in list(self.registered_documents.keys()):
            if sid not in PromptServer.instance.sockets.keys():
                del self.registered_documents[sid]
                has_changed = True

        if not has_changed:
            return

        krita_documents = self.get_registered_documents().model_dump()
        await PromptServer.instance.send("krita::documents::update", krita_documents)

    def _prune_stale_sids(self):
        PromptServer.instance.loop.create_task(self.prune_stale_sids_async())

    async def _unregister_documents_by_sid_async(self, sid) -> None:
        if sid in self.registered_documents.keys():
            del self.registered_documents[sid]
    
    def document_id_to_sid(self, document_id: str) -> str | None:
        return next((
            sid
            for sid, document_set in self.registered_documents.items()
            for d in document_set
            if d == document_id
        ), None)


def _ensure_unique_id(document_id, registered_documents) -> str:
    converted_id = document_id

    if document_id in registered_documents:
        regex = rf"{re.escape(document_id)} \((\d+)\)"
        same_ids = [i for i in registered_documents if re.match(regex, i)]
        matches = [re.fullmatch(regex, i) for i in same_ids]
        used_deduplicate_ids = set([int(m.group(1)) for m in matches if m is not None])
        next_deduplicate_id = len(used_deduplicate_ids) + 1

        for i in range(0, len(used_deduplicate_ids)):
            if i + 1 not in used_deduplicate_ids:
                next_deduplicate_id = i + 1
                break

        converted_id = f"{document_id} ({next_deduplicate_id})"

    return converted_id


api = KritaApi()
