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


class PrunedKritaWorkflow(BaseModel):
    name: str
    inputs: list[Node]
    outputs: list[Node]


class UpdateWorkflowsRequest(BaseModel):
    name: str
    workflows: dict[str, list[Node]]


class UpdateKritaDocumentsRequest(BaseModel):
    documents: list[str]


class DocumentMappingResponse(BaseModel):
    mapping: dict[str, str]
