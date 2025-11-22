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


class SaveImageState(BaseModel):
    id: int
    insert_direction: Literal["above", "below"]
    path: list[FlatLayerToken]
    visible: bool


class PersistentLayer(BaseModel):
    quuid: Any
    path: list[FlatLayerToken] | None = None
    visible: bool = True
