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
    quuid: str
    type: Literal["layer", "group_start", "group_end", "target"]


class SaveImageState(BaseModel):
    id: int
    insert_direction: Literal["above", "below"]
    flat_layer_path: list[FlatLayerToken]
