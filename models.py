from typing import Literal

from pydantic import BaseModel


class Node(BaseModel):
    id: int
    type: str
    name: str
    direction: Literal["input", "output"] | None = None


class UpdateWorkflowsRequest(BaseModel):
    name: str
    workflows: dict[str, list[Node]]

    @classmethod
    def default(cls) -> "UpdateWorkflowsRequest":
        return cls(name="", workflows={})


class UpdateKritaDocumentsRequest(BaseModel):
    sid: str
    documents: list[str]


class DocumentMappingResponse(BaseModel):
    mapping: dict[str, str]


class KritaDocuments(BaseModel):
    documents: list[str]
