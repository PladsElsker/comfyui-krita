from typing import Any, Dict, List
from pydantic import BaseModel


class StatusRequest(BaseModel):
    status: Dict[str, Any]
    sid: str


class Node(BaseModel):
    id: int
    type: str
    name: str


class PrunedKritaWorkflow(BaseModel):
    name: str
    inputs: List[Node]
    outputs: List[Node]


class UpdateWorkflowsRequest(BaseModel):
    name: str
    workflows: Dict[str, List[Node]]


class UpdateKritaDocumentsRequest(BaseModel):
    documents: List[str]


class DocumentMappingResponse(BaseModel):
    mapping: Dict[str, str]
