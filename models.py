from pydantic import BaseModel


class Node(BaseModel):
    id: int
    type: str
    name: str


class UpdateWorkflowsRequest(BaseModel):
    name: str
    workflows: dict[str, list[Node]]

    @classmethod
    def default(cls) -> "UpdateWorkflowsRequest":
        return cls(name="", workflows={})


class PrunedKritaWorkflow(BaseModel):
    name: str
    inputs: list[Node]
    outputs: list[Node]


class UpdateKritaDocumentsRequest(BaseModel):
    sid: str
    documents: list[str]


class DocumentMappingResponse(BaseModel):
    mapping: dict[str, str]


class KritaDocuments(BaseModel):
    documents: list[str]


class UpdateKritaWorkflowRequest(BaseModel):
    id: str
    workflow: PrunedKritaWorkflow
