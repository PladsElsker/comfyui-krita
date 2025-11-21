from typing import ClassVar

from krita import Document, Krita, Node
from pydantic import BaseModel
from PyQt5.QtCore import QObject, QTimer, QUuid


class PersistentLayerManager:
    documents: ClassVar[list[Document]] = []
    managers: ClassVar[dict[int, "PersistentLayerManager"]] = {}

    def __init__(self, document: Document, refresh_ms: int = 2000) -> None:
        self.document = document
        self.refresh_ms = refresh_ms
        self.registered_layers: dict[QUuid, PersistentLayer] = {}
        self.reverse_lookup: dict[QUuid, QUuid] = {}
        self.expected: dict[PersistentLayer, QUuid | None] = {}

        self._schedule_step()

    def create(self, name: str) -> QUuid:
        uuid = QUuid()
        layer = PersistentLayer(name=name)
        self.registered_layers[uuid] = layer
        return uuid

    def delete(self, uuid: QUuid) -> None:
        if uuid not in self.registered_layers:
            return

        self.registered_layers[uuid].scheduled_for_deletion = True

    def exists(self, uuid: QUuid) -> bool:
        if uuid not in self.registered_layers:
            return False

        return not self.registered_layers[uuid].scheduled_for_deletion

    def rename(self, uuid: QUuid, name: str) -> None:
        if uuid not in self.registered_layers:
            message = f"Layer {uuid} has not been created"
            raise ValueError(message)

        self.registered_layers[uuid].name = name

    def select(self, uuid: QUuid) -> None:
        if uuid not in self.registered_layers:
            return

        if self.registered_layers[uuid] is None:
            return

        persistent_layer = self.registered_layers[uuid]

        if persistent_layer.linked_uuid is None:
            return

        match = self._validate_uuid(persistent_layer.linked_uuid)

        if match is None:
            return

        self.document.setActiveNode(match)

    def _step(self) -> None:
        roots = self.document.topLevelNodes()
        existing_layers = [PersistentLayer.from_krita(layer) for layer in LayerUtils.flatten_tree(roots)]
        actual_state = {self.reverse_lookup[ex.linked_uuid]: ex for ex in existing_layers if ex.linked_uuid is not None}

        additions = {uuid: layer for uuid, layer in self.registered_layers.items() if layer.linked_uuid is None}
        modifications = {
            uuid: layer for uuid, layer in self.registered_layers.items() if layer.linked_uuid is not None and actual_state[uuid].name != layer.name
        }
        deletions = {uuid: layer for uuid, layer in self.registered_layers.items() if layer.scheduled_for_deletion}

        if len(deletions) > 0:
            uuid = next(iter(deletions.keys()))
            to_delete = deletions[uuid]
            self._delete(uuid, to_delete)
        elif len(additions) > 0:
            uuid = next(iter(additions.keys()))
            to_add = additions[uuid]
            self._create(uuid, to_add)
        elif len(modifications) > 0:
            uuid = next(iter(modifications.keys()))
            initial = existing_layers[uuid]
            new = modifications[uuid]
            self._modify(uuid, initial, new)

        self._schedule_step()

    def _delete(self, uuid: QUuid, layer: "PersistentLayer") -> None:
        def _remove_id() -> None:
            linked_uuid = self.registered_layers[uuid].linked_uuid

            if linked_uuid is not None:
                self.reverse_lookup.pop(linked_uuid, None)

            self.registered_layers.pop(uuid, None)

        if layer.linked_uuid is None:
            _remove_id()
            return

        match = self._validate_uuid(layer.linked_uuid)

        if match is None:
            _remove_id()
            return

        match.setLocked(False)
        parent = match.parent()
        parent = self.document.rootNode() if parent is None else parent

        if isinstance(parent, Node):
            parent.removeChildNode(match)

        _remove_id()

    def _create(self, uuid: QUuid, layer: "PersistentLayer") -> None:
        if layer.linked_uuid is not None:
            return

        root = self.document.rootNode()
        top = next(iter(reversed(self.document.topLevelNodes())), None)
        new_layer = self.document.createNode(layer.name, "vectorlayer")
        node_id = new_layer.uniqueId()
        self.registered_layers[uuid].linked_uuid = node_id
        self.reverse_lookup[node_id] = uuid
        new_layer.setOpacity(0)
        new_layer.setVisible(False)
        new_layer.setAlphaLocked(True)

        if isinstance(top, Node | None):
            root.addChildNode(new_layer, top)  # type: ignore

    def _modify(self, uuid: QUuid, _from: "PersistentLayer", _to: "PersistentLayer") -> None:
        assert _from.linked_uuid is not None  # noqa: S101
        assert _to.linked_uuid is not None  # noqa: S101

        match = self._validate_uuid(_to.linked_uuid)

        if match is None:
            self.registered_layers.pop(uuid, None)
            return

        match.setName(_to.name)

    def _schedule_step(self) -> None:
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._step)
        self._timer.start(self.refresh_ms)

    def _validate_uuid(self, uuid: QUuid) -> Node | None:
        if uuid not in self.registered_layers:
            return None

        layer = self.registered_layers[uuid]
        roots = self.document.topLevelNodes()
        all_layers = LayerUtils.flatten_tree(roots)

        return next((existing_layer for existing_layer in all_layers if existing_layer.uniqueId() == layer.linked_uuid), None)

    @classmethod
    def get_by_document(cls, document: Document) -> "PersistentLayerManager":
        if document in cls.documents:
            index = cls.documents.index(document)
        else:
            cls.documents.append(document)
            index = len(cls.documents) - 1

        if index not in cls.managers:
            cls.managers[index] = cls(document)

        return cls.managers[index]


class PersistentLayer(BaseModel):
    name: str
    linked_uuid: QUuid | None = None
    scheduled_for_deletion: bool = False

    @classmethod
    def from_krita(cls, layer: Node) -> "PersistentLayer":
        return cls(
            name=layer.name(),
            linked_uuid=layer.uniqueId(),
        )


class LayerUtils:
    @staticmethod
    def flatten_tree(roots: list[Node]) -> list[Node]:
        remaining = list(reversed(roots))
        flat_list = []

        while len(remaining) > 0:
            node = remaining.pop()
            flat_list.append(node)
            children = [n for n in reversed(node.children()) if isinstance(n, Node)]
            remaining += children

        return flat_list


class LayersManager(QObject):
    documents: ClassVar[list[Document]] = []
    managers: ClassVar[dict[int, "LayersManager"]] = {}

    def __init__(self, document: Document) -> None:
        super().__init__()
        self._krita = Krita.instance()
        self.document = document
        self.managed_layers: dict[QUuid, Node] = {}

    def create(self, name: str) -> QUuid | None:
        root = self.document.rootNode()
        top = next(iter(reversed(self.document.topLevelNodes())), None)
        new_layer = self.document.createNode(name, "vectorlayer")
        node_id = new_layer.uniqueId()
        self.managed_layers[node_id] = new_layer
        new_layer.setOpacity(0)
        new_layer.setVisible(False)
        new_layer.setAlphaLocked(True)

        if isinstance(top, Node | None):

            def _slot() -> None:
                root.addChildNode(new_layer, top)  # type: ignore

            flush_timer = QTimer(self)
            flush_timer.setSingleShot(True)
            flush_timer.timeout.connect(_slot)
            flush_timer.start(50)

        return node_id

    def delete(self, uuid: QUuid) -> None:
        if uuid not in self.managed_layers:
            return

        match = self._validate_uuid(uuid)

        if not match:
            return

        match.setLocked(False)

        parent = match.parent()
        parent = self.document.rootNode() if parent is None else parent

        self.managed_layers.pop(uuid, None)

        if isinstance(parent, Node):

            def _slot() -> None:
                parent.removeChildNode(match)

            flush_timer = QTimer(self)
            flush_timer.setSingleShot(True)
            flush_timer.timeout.connect(_slot)
            flush_timer.start(50)

    def exists(self, uuid: QUuid) -> bool:
        return uuid in self.managed_layers

    def rename(self, uuid: QUuid, name: str) -> None:
        match = self._validate_uuid(uuid)

        if match is None:
            return

        match.setName(name)

    def select(self, uuid: QUuid) -> None:
        if uuid not in self.managed_layers:
            return

        self.document.setActiveNode(self.managed_layers[uuid])

    @classmethod
    def get_by_document(cls, document: Document) -> "LayersManager":
        if document in cls.documents:
            index = cls.documents.index(document)
        else:
            cls.documents.append(document)
            index = len(cls.documents) - 1

        if index not in cls.managers:
            cls.managers[index] = cls(document)

        return cls.managers[index]

    def _validate_uuid(self, uuid: QUuid) -> Node | None:
        if uuid not in self.managed_layers:
            return None

        layer = self.managed_layers[uuid]
        roots = self.document.topLevelNodes()
        all_layers = LayerUtils.flatten_tree(roots)

        return next((existing_layer for existing_layer in all_layers if existing_layer.uniqueId() == layer.uniqueId()), None)
