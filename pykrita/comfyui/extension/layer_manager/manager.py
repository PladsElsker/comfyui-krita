from abc import ABC, abstractmethod
from typing import ClassVar

from krita import Document, Window

from ..models import PersistentLayer
from .notifier import PersistentLayerNotifier


class LayerManager(ABC):
    documents: ClassVar[list[Document]] = []
    managers: ClassVar[dict[int, "LayerManager"]] = {}

    def __init__(self, window: Window, document: Document) -> None:
        super().__init__()
        self.window = window
        self.document = document

    @abstractmethod
    def create(self, name: str, path: list | None = None) -> PersistentLayer: ...

    @abstractmethod
    def delete(self, persistent_layer: PersistentLayer) -> None: ...

    @abstractmethod
    def exists(self, persistent_layer: PersistentLayer) -> bool: ...

    @abstractmethod
    def select(self, persistent_layer: PersistentLayer) -> None: ...

    @abstractmethod
    def notifier(self, persistent_layer: PersistentLayer) -> PersistentLayerNotifier: ...

    @abstractmethod
    def show(self, persistent_layer: PersistentLayer) -> None: ...

    @abstractmethod
    def hide(self, persistent_layer: PersistentLayer) -> None: ...

    @classmethod
    def get_by_window_and_document(cls, window: Window, document: Document) -> "LayerManager":
        if document in cls.documents:
            index = cls.documents.index(document)
        else:
            cls.documents.append(document)
            index = len(cls.documents) - 1

        if index not in cls.managers:
            cls.managers[index] = cls(window, document)

        return cls.managers[index]
