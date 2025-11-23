import contextlib
from typing import Any

from krita import Document, Node, Window
from pydantic import BaseModel
from PyQt5.QtCore import QTimer, QUuid

from ..models import FlatLayerToken, PersistentLayer
from .manager import LayerManager
from .notifier import PersistentLayerNotifier
from .utils import LayerRelativePath, LayerUtils


class PersistentLayerManager(LayerManager):
    def __init__(self, window: Window, document: Document, refresh_ms: int = 300, default_layer_type: str = "vectorlayer") -> None:
        super().__init__(window, document)
        self.refresh_ms = refresh_ms
        self.default_layer_type = default_layer_type
        self.registered_layers: dict[PersistentId, PersistentLayerInternalState] = {}
        self.reverse_lookup: dict[VolatileId, PersistentId] = {}
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._step)
        self._schedule_step_slow()
        self.layer_notifiers: dict[PersistentId, PersistentLayerNotifier] = {}

    def create(self, name: str, path: list[FlatLayerToken] | None = None) -> PersistentLayer:
        uuid = QUuid.createUuid()

        if path is None:
            roots = self.document.topLevelNodes()
            tokens = LayerUtils.to_flat_tokens(roots)
            tokens.append(FlatLayerToken(quuid=None, type="target"))
            path = tokens

        layer = PersistentLayerInternalState(name=name, path=path, rendered=True)
        self.registered_layers[uuid] = layer
        return PersistentLayer(quuid=uuid)

    def delete(self, persistent_layer: PersistentLayer) -> None:
        if persistent_layer.quuid not in self.registered_layers:
            return

        self.registered_layers[persistent_layer.quuid].scheduled_for_deletion = True

    def exists(self, persistent_layer: PersistentLayer) -> bool:
        if persistent_layer.quuid not in self.registered_layers:
            return False

        return not self.registered_layers[persistent_layer.quuid].scheduled_for_deletion

    def select(self, persistent_layer: PersistentLayer) -> None:
        if persistent_layer.quuid not in self.registered_layers:
            return

        if self.registered_layers[persistent_layer.quuid] is None:
            return

        internal_layer = self.registered_layers[persistent_layer.quuid]

        if internal_layer.linked_uuid is None:
            return

        match = self._validate_uuid(internal_layer.linked_uuid)

        if match is None:
            return

        self.document.setActiveNode(match)

    def notifier(self, persistent_layer: PersistentLayer) -> PersistentLayerNotifier:
        if not self.exists(persistent_layer):
            message = f"Layer {persistent_layer.model_dump()} does not exist"
            raise ValueError(message)

        return self._ensure_notifier(persistent_layer.quuid)

    def show(self, persistent_layer: PersistentLayer) -> None:
        if persistent_layer.quuid not in self.registered_layers:
            return

        self.registered_layers[persistent_layer.quuid].rendered = True

    def hide(self, persistent_layer: PersistentLayer) -> None:
        if persistent_layer.quuid not in self.registered_layers:
            return

        self.registered_layers[persistent_layer.quuid].rendered = False

    def _step(self) -> None:
        active_view = self.window.activeView()

        if active_view is None:
            return

        active_document = active_view.document()

        if active_document is None:
            return

        # Krita will crash if we try to modify the layer tree in an inactive document.
        if self.document != active_document:
            self._schedule_step_slow()
            return

        additions, modifications, deletions, actual_state = PersistentLayerInternalState.compute_diffs(self)

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

    def _delete(self, uuid: "PersistentId", layer: "PersistentLayerInternalState") -> None:
        def _remove_id() -> None:
            linked_uuid = self.registered_layers[uuid].linked_uuid
            self.registered_layers[uuid].linked_uuid = None

            if self.registered_layers[uuid].scheduled_for_deletion:
                self.registered_layers.pop(uuid, None)

                if linked_uuid is not None:
                    self.reverse_lookup.pop(linked_uuid, None)

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
            with contextlib.suppress(Exception):
                parent.removeChildNode(match)

        _remove_id()

    def _create(self, uuid: "PersistentId", layer: "PersistentLayerInternalState") -> None:
        new_layer = self.document.createNode(layer.name, self.default_layer_type)

        if new_layer is None:
            return

        node_id = new_layer.uniqueId()
        layer.linked_uuid = node_id
        layer.last_linked_uuid = node_id
        self.reverse_lookup[node_id] = uuid

        for token in layer.path:
            if token.type == "target":
                token.quuid = node_id

        new_layer.setOpacity(0)
        new_layer.setVisible(False)
        new_layer.setAlphaLocked(True)
        res = self._rebase(layer)

        if res is None:
            return

        rebased, rel_path = res

        if rel_path is None:
            return

        saved_path = layer.path
        try:
            layer.path = rebased
            rel_path.parent.addChildNode(new_layer, rel_path.sibling)  # type: ignore
        except Exception:  # noqa: BLE001
            layer.path = saved_path

    def _modify(self, uuid: "PersistentId", _from: "PersistentLayerInternalState", _to: "PersistentLayerInternalState") -> None:
        notifier = self._ensure_notifier(uuid)

        _to.path = _from.path

        if _to.name != _from.name:
            _to.name = _from.name
            notifier.name_changed.emit(_to.name)

        if _to.linked_uuid is None and _to.last_linked_uuid == _from.linked_uuid:
            _to.linked_uuid = _to.last_linked_uuid
            _to.rendered = True
            notifier.user_rendered.emit()
        elif _from.linked_uuid is None:
            _to.rendered = False
            _to.linked_uuid = None
            notifier.user_unrendered.emit()
            return

        assert _to.linked_uuid is not None  # noqa: S101

        match = self._validate_uuid(_to.linked_uuid)

        if match is None:
            self.registered_layers.pop(uuid, None)
            return

        match.setLocked(False)
        match.setAlphaLocked(True)
        match.setVisible(False)
        match.setOpacity(0)

    def _schedule_step_slow(self) -> None:
        self._timer.start(self.refresh_ms)

    def _schedule_step_immediate(self) -> None:
        self._timer.start(1)

    def _validate_uuid(self, uuid: "VolatileId") -> Node | None:
        roots = self.document.topLevelNodes()
        all_layers = LayerUtils.flatten_tree(roots)

        return next((existing_layer for existing_layer in all_layers if existing_layer.uniqueId() == uuid), None)

    def _ensure_notifier(self, uuid: "PersistentId") -> PersistentLayerNotifier:
        if uuid is not None and uuid not in self.layer_notifiers:
            self.layer_notifiers[uuid] = PersistentLayerNotifier()

        return self.layer_notifiers[uuid]

    def _rebase(self, to: "PersistentLayerInternalState") -> "tuple[list[FlatLayerToken], LayerRelativePath] | None":
        roots = self.document.topLevelNodes()
        tokens = LayerUtils.to_flat_tokens(roots)
        tokens = [token for token in tokens if token.quuid != to.linked_uuid]
        rebased, parent_token, sibling_token = LayerUtils.rebase(to.path, tokens)
        all_layers = LayerUtils.flatten_tree(roots)

        if parent_token is None:
            parent = self.document.rootNode()
        else:
            parent = next((layer_search for layer_search in all_layers if layer_search.uniqueId() == parent_token.quuid), None)

        if parent is None:
            return None

        if sibling_token is not None:
            sibling = next((layer_search for layer_search in all_layers if layer_search.uniqueId() == sibling_token.quuid), None)
        else:
            sibling = None

        return rebased, LayerRelativePath(parent=parent, sibling=sibling)


class PersistentLayerInternalState(BaseModel):
    name: str
    linked_uuid: Any | None = None
    last_linked_uuid: Any | None = None
    scheduled_for_deletion: bool = False
    locked: bool = False
    alpha_locked: bool = True
    visible: bool = False
    opacity: int = 0
    type: str = "vectorlayer"
    path: list[FlatLayerToken]
    rendered: bool = False

    def should_be_deleted(self, actual: "PersistentLayerInternalState") -> bool:  # noqa: ARG002
        if not self.rendered and self.linked_uuid is not None:
            return True

        return self.scheduled_for_deletion

    def should_be_created(self, actual: "PersistentLayerInternalState") -> bool:
        if actual.linked_uuid is None and self.linked_uuid is not None:
            return False

        if not self.rendered:
            return False

        if self.scheduled_for_deletion:
            return False

        if self.last_linked_uuid is not None and actual.linked_uuid == self.last_linked_uuid:
            return False

        return self.linked_uuid is None or actual.linked_uuid != self.linked_uuid

    def should_be_updated(self, actual: "PersistentLayerInternalState") -> bool:
        if self.linked_uuid is None and self.last_linked_uuid is not None and actual.linked_uuid == self.last_linked_uuid:
            return True

        if actual.linked_uuid is None and self.linked_uuid is not None:
            return True

        if not self.rendered:
            return False

        if self.linked_uuid is None:
            return False

        return (
            self.name != actual.name
            or self.locked != actual.locked
            or self.visible != actual.visible
            or self.opacity != actual.opacity
            or not self.same_path(actual.path)
        )

    def same_path(self, path: list[FlatLayerToken]) -> bool:
        return tuple(str(t.quuid) for t in self.path) == tuple(str(t.quuid) for t in path)

    @staticmethod
    def compute_diffs(manager: PersistentLayerManager) -> tuple:
        roots = manager.document.topLevelNodes()
        tokens = LayerUtils.to_flat_tokens(roots)
        existing_layers = [PersistentLayerInternalState.from_krita(layer, tokens) for layer in LayerUtils.flatten_tree(roots)]
        actual = {
            manager.reverse_lookup[existing.linked_uuid]: existing
            for existing in existing_layers
            if existing.linked_uuid is not None and existing.linked_uuid in manager.reverse_lookup
        }

        for uuid, layer in manager.registered_layers.items():
            if uuid not in actual:
                actual[uuid] = PersistentLayerInternalState.model_validate(layer.model_dump())
                actual[uuid].linked_uuid = None

        additions = {uuid: layer for uuid, layer in manager.registered_layers.items() if layer.should_be_created(actual[uuid])}
        modifications = {uuid: layer for uuid, layer in manager.registered_layers.items() if layer.should_be_updated(actual[uuid])}
        deletions = {uuid: layer for uuid, layer in manager.registered_layers.items() if layer.should_be_deleted(actual[uuid])}

        return additions, modifications, deletions, actual

    @classmethod
    def from_krita(cls, layer: Node, empty_path: list[FlatLayerToken]) -> "PersistentLayerInternalState":
        path = list(empty_path)

        for i, token in enumerate(path):
            if token.quuid == layer.uniqueId():
                path[i] = FlatLayerToken(quuid=layer.uniqueId(), type="target")
                break

        return cls(
            name=layer.name(),
            linked_uuid=layer.uniqueId(),
            locked=layer.locked(),
            visible=layer.visible(),
            opacity=layer.opacity(),
            path=path,
            rendered=True,
        )


class PersistentId(QUuid):
    pass


class VolatileId(QUuid):
    pass
