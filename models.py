from typing import Dict, List
from pydantic import BaseModel


class Node(BaseModel):
    id: int
    type: str
    name: str


class UpdateWorkflowsRequest(BaseModel):
    name: str
    workflows: Dict[str, List[Node]]


class PrunedKritaWorkflow(BaseModel):
    name: str
    inputs: List[Node]
    outputs: List[Node]


class UpdateKritaDocumentsRequest(BaseModel):
    sid: str
    documents: List[str]


class DocumentMappingResponse(BaseModel):
    mapping: Dict[str, str]


class KritaDocuments(BaseModel):
    documents: List[str]


class UpdateKritaWorkflowRequest(BaseModel):
    id: str
    workflow: PrunedKritaWorkflow
