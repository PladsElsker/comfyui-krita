from typing import Any, ClassVar

from krita import Document, Node
from pydantic import BaseModel
from PyQt5.QtCore import QTimer, QUuid


class PersistentLayerManager:
    documents: ClassVar[list[Document]] = []
    managers: ClassVar[dict[int, "PersistentLayerManager"]] = {}

    def __init__(self, document: Document, refresh_ms: int = 300) -> None:
        self.document = document
        self.refresh_ms = refresh_ms
        self.registered_layers: dict[QUuid, PersistentLayer] = {}
        self.reverse_lookup: dict[QUuid, QUuid] = {}
        self.expected: dict[PersistentLayer, QUuid | None] = {}
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._step)
        self._schedule_step_slow()

    def create(self, name: str) -> QUuid:
        uuid = QUuid.createUuid()
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
        actual_state = {
            self.reverse_lookup[ex.linked_uuid]: ex for ex in existing_layers if ex.linked_uuid is not None and ex.linked_uuid in self.reverse_lookup
        }

        additions = {uuid: layer for uuid, layer in self.registered_layers.items() if layer.linked_uuid is None or uuid not in actual_state}
        modifications = {
            uuid: layer
            for uuid, layer in self.registered_layers.items()
            if layer.linked_uuid is not None and (uuid in actual_state and PersistentLayer.state_differs(actual_state[uuid], layer))
        }
        deletions = {uuid: layer for uuid, layer in self.registered_layers.items() if layer.scheduled_for_deletion}

        if len(deletions) > 1 or len(additions) > 1 or len(modifications) > 1:
            pass

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
            initial = actual_state[uuid]
            new = modifications[uuid]
            self._modify(uuid, initial, new)

        if len(deletions) > 1 or len(additions) > 1 or len(modifications) > 1:
            self._schedule_step_immediate()
        else:
            self._schedule_step_slow()

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
        root = self.document.rootNode()
        top = next(iter(reversed(self.document.topLevelNodes())), None)
        new_layer = self.document.createNode(layer.name, "vectorlayer")

        if new_layer is None:
            return

        node_id = new_layer.uniqueId()

        if layer.linked_uuid is not None:
            self.reverse_lookup.pop(node_id, None)

        layer.linked_uuid = node_id
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
        match.setLocked(False)
        match.setAlphaLocked(True)
        match.setVisible(False)
        match.setOpacity(0)

    def _schedule_step_slow(self) -> None:
        self._timer.start(self.refresh_ms)

    def _schedule_step_immediate(self) -> None:
        self._timer.start(1)

    def _validate_uuid(self, uuid: QUuid) -> Node | None:
        roots = self.document.topLevelNodes()
        all_layers = LayerUtils.flatten_tree(roots)

        return next((existing_layer for existing_layer in all_layers if existing_layer.uniqueId() == uuid), None)

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
    linked_uuid: Any | None = None
    scheduled_for_deletion: bool = False
    locked: bool = False
    alpha_locked: bool = True
    visible: bool = False
    opacity: int = 0
    type: str = "vectorlayer"

    @classmethod
    def from_krita(cls, layer: Node) -> "PersistentLayer":
        return cls(
            name=layer.name(),
            linked_uuid=layer.uniqueId(),
            locked=layer.locked(),
            visible=layer.visible(),
            opacity=layer.opacity(),
        )

    @staticmethod
    def state_differs(layer1: "PersistentLayer", layer2: "PersistentLayer") -> bool:
        return layer1.name != layer2.name or layer1.locked != layer2.locked or layer1.visible != layer2.visible or layer1.opacity != layer2.opacity


class LayerUtils:
    @staticmethod
    def flatten_tree(roots: list[Node]) -> list[Node]:
        remaining = list(reversed(roots))
        flat_list = []

        while len(remaining) > 0:
            node = remaining.pop()
            flat_list.append(node)
            children = [n for n in reversed(node.childNodes()) if isinstance(n, Node)]
            remaining += children

        return flat_list
