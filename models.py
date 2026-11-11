from typing import Literal

from pydantic import BaseModel, Field


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
    previous_mappings: dict[str, str] = Field(default_factory=dict)


class DocumentMappingResponse(BaseModel):
    mapping: dict[str, str]


class KritaDocuments(BaseModel):
    documents: list[str]


class FlatLayerToken(BaseModel):
    quuid: str | None
    type: Literal["layer", "group_start", "group_end", "target"]


class SaveImageState(BaseModel):
    id: int
    type: Literal["KritaSaveImage-15347"]
    document_id: str
    insert_direction: Literal["above", "below"]
    path: list[FlatLayerToken]
    layer_name: str


class LoadImageState(BaseModel):
    id: int
    type: Literal["KritaLoadImage-15347"]
    document_id: str
    layer_ids: list[str] = Field(default_factory=list)
    layer_names: list[str] = Field(default_factory=list)
    snapshot_revision: str = ""
    selection_generation: int = 0
    snapshot_pending: bool = False


class LoadImageExecutionState(BaseModel):
    id: int
    type: Literal["KritaLoadImage-15347"]
    document_id: str
    snapshot_revision: str = ""


KritaNodeState = SaveImageState | LoadImageState


class KritaNodeStateUpdate(BaseModel):
    deleted: bool = False
    state: KritaNodeState | None = None
    document_id: str | None = None
    id: int | None = None
    type: str | None = None


class LayerCreateNotification(BaseModel):
    transfer_id: str
    state: SaveImageState
    batch_index: int = 0
    batch_size: int = 1
