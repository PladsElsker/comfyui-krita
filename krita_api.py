import re
import inspect
from typing import Dict

from server import PromptServer

from .models import KritaDocuments, UpdateKritaWorkflowRequest


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
    async def update_workflow(self, document_id, pruned_workflow):
        update_workflow_request = UpdateKritaWorkflowRequest(id=document_id, workflow=pruned_workflow)
        sid = next(
            sid
            for sid, document_set in self.registered_documents.items()
            for d in document_set
            if d == document_id
        )

        if sid:
            await PromptServer.instance.send("krita::workflow::update", update_workflow_request.model_dump(), sid)

    def get_registered_documents(self) -> KritaDocuments:
        return KritaDocuments(documents=sorted([
            document_id
            for document_set in self.registered_documents.values()
            for document_id in document_set
        ]))

    async def prune_stale_sids_async(self):
        for sid in list(self.registered_documents.keys()):
            if sid not in PromptServer.instance.sockets.keys():
                del self.registered_documents[sid]

        krita_documents = self.get_registered_documents().model_dump()
        await PromptServer.instance.send("krita::documents::update", krita_documents)

    def _prune_stale_sids(self):
        for sid in list(self.registered_documents.keys()):
            if sid not in PromptServer.instance.sockets:
                del self.registered_documents[sid]

        krita_documents = self.get_registered_documents().model_dump()
        task = PromptServer.instance.send("krita::documents::update", krita_documents)
        PromptServer.instance.loop.create_task(task)

    async def _unregister_documents_by_sid_async(self, sid) -> None:
        if sid in self.registered_documents.keys():
            del self.registered_documents[sid]


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
