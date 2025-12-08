from typing import Any, Literal

from pydantic import BaseModel

NodeDirection = Literal["input", "output"]


class StatusRequest(BaseModel):
    status: dict[str, Any]
    sid: str


class Node(BaseModel):
    id: int
    type: str
    name: str
    direction: NodeDirection


class UpdateWorkflowsRequest(BaseModel):
    name: str
    workflows: dict[str, list[Node]]


class UpdateDocumentsRequest(BaseModel):
    documents: list[str]
    previous_mappings: dict[str, str]


class DocumentMappingResponse(BaseModel):
    mapping: dict[str, str]


class FlatLayerToken(BaseModel):
    quuid: Any | None
    type: Literal["layer", "group_start", "group_end", "target"]

    def __hash__(self) -> int:
        q = str(self.quuid if self.quuid is not None else "")
        return hash(q + self.type)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FlatLayerToken):
            return False

        return str(self.quuid) == str(other.quuid)


class UiNodeState(BaseModel):
    id: int
    type: str
    document_id: str


class SaveImageState(UiNodeState):
    insert_direction: Literal["above", "below"]
    path: list[FlatLayerToken]
    visible: bool
    layer_name: str


KritaLayerType = Literal[
    "paintlayer",
    "vectorlayer",
    "grouplayer",
    "filelayer",
    "filterlayer",
    "filllayer",
    "clonelayer",
    "transformmask",
    "referenceimageslayer",
    "transparencymask",
    "filtermask",
    "selectionmask",
    "colorizemask",
]
