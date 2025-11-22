import contextlib
import difflib
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, cast

from krita import Document, Node
from pydantic import BaseModel
from PyQt5.QtCore import QObject, QTimer, QUuid, pyqtBoundSignal, pyqtSignal

from .models import FlatLayerToken, PersistentLayer


class PersistentLayerManager:
    documents: ClassVar[list[Document]] = []
    managers: ClassVar[dict[int, "PersistentLayerManager"]] = {}

    def __init__(self, document: Document, refresh_ms: int = 300, default_layer_type: str = "vectorlayer") -> None:
        self.document = document
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

    def rename(self, persistent_layer: PersistentLayer, name: str) -> None:
        if persistent_layer.quuid not in self.registered_layers:
            message = f"Layer {persistent_layer.quuid} has not been created"
            raise ValueError(message)

        self.registered_layers[persistent_layer.quuid].name = name

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

    def notifier(self, persistent_layer: PersistentLayer) -> "PersistentLayerNotifier | None":
        if not self.exists(persistent_layer):
            message = f"Layer {persistent_layer.model_dump()} does not exist"
            raise ValueError(message)

        if persistent_layer.quuid not in self.layer_notifiers:
            self.layer_notifiers[persistent_layer.quuid] = PersistentLayerNotifier()

        return self.layer_notifiers[persistent_layer.quuid]

    def show(self, persistent_layer: PersistentLayer) -> None:
        if persistent_layer.quuid not in self.registered_layers:
            return

        self.registered_layers[persistent_layer.quuid].rendered = True

    def hide(self, persistent_layer: PersistentLayer) -> None:
        if persistent_layer.quuid not in self.registered_layers:
            return

        self.registered_layers[persistent_layer.quuid].rendered = False

    def _step(self) -> None:
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

            if linked_uuid is not None:
                self.reverse_lookup.pop(linked_uuid, None)

            if self.registered_layers[uuid].scheduled_for_deletion:
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
            with contextlib.suppress(Exception):
                parent.removeChildNode(match)

        _remove_id()

    def _create(self, uuid: "PersistentId", layer: "PersistentLayerInternalState") -> None:
        new_layer = self.document.createNode(layer.name, self.default_layer_type)

        if new_layer is None:
            return

        node_id = new_layer.uniqueId()
        layer.linked_uuid = node_id
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

        _to.path = _from.path

    def _schedule_step_slow(self) -> None:
        self._timer.start(self.refresh_ms)

    def _schedule_step_immediate(self) -> None:
        self._timer.start(1)

    def _validate_uuid(self, uuid: "VolatileId") -> Node | None:
        roots = self.document.topLevelNodes()
        all_layers = LayerUtils.flatten_tree(roots)

        return next((existing_layer for existing_layer in all_layers if existing_layer.uniqueId() == uuid), None)

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


class PersistentLayerInternalState(BaseModel):
    name: str
    linked_uuid: Any | None = None
    scheduled_for_deletion: bool = False
    locked: bool = False
    alpha_locked: bool = True
    visible: bool = False
    opacity: int = 0
    type: str = "vectorlayer"
    path: list[FlatLayerToken]
    rendered: bool = False

    def should_be_deleted(self) -> bool:
        if not self.rendered and self.linked_uuid is not None:
            return True

        return self.scheduled_for_deletion

    def should_be_created(self, actual: "dict[PersistentId, PersistentLayerInternalState]") -> bool:
        if not self.rendered:
            return False

        if self.scheduled_for_deletion:
            return False

        return self.linked_uuid is None or self.linked_uuid not in [layer.linked_uuid for layer in actual.values()]

    def should_be_updated(self, actual: "dict[PersistentId, PersistentLayerInternalState]", uuid: "PersistentId") -> bool:
        if not self.rendered:
            return False

        if self.linked_uuid is None:
            return False

        if uuid not in actual:
            return False

        other = actual[uuid]

        return (
            self.name != other.name
            or self.locked != other.locked
            or self.visible != other.visible
            or self.opacity != other.opacity
            or not self.same_path(other.path)
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

        additions = {uuid: layer for uuid, layer in manager.registered_layers.items() if layer.should_be_created(actual)}
        modifications = {uuid: layer for uuid, layer in manager.registered_layers.items() if layer.should_be_updated(actual, uuid)}
        deletions = {uuid: layer for uuid, layer in manager.registered_layers.items() if layer.should_be_deleted()}

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


class PersistentLayerNotifier(QObject):
    on_layer_moved = cast("pyqtBoundSignal", pyqtSignal())
    on_layer_deleted = cast("pyqtBoundSignal", pyqtSignal())
    on_layer_created = cast("pyqtBoundSignal", pyqtSignal())


class PersistentId(QUuid):
    pass


class VolatileId(QUuid):
    pass


@dataclass
class LayerRelativePath:
    parent: Node
    sibling: Node | None


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

    @classmethod
    def to_flat_tokens(cls, roots: list[Node]) -> list[FlatLayerToken]:
        result: list[FlatLayerToken] = []

        for node in roots:
            node_children = node.childNodes()
            is_parent = len(node_children) > 0
            if is_parent:
                result.append(FlatLayerToken(quuid=node.uniqueId(), type="group_start"))
                result += cls.to_flat_tokens(node_children)
                result.append(FlatLayerToken(quuid=node.uniqueId(), type="group_end"))
            else:
                result.append(FlatLayerToken(quuid=node.uniqueId(), type="layer"))

        return result

    @classmethod
    def rebase(  # noqa: C901, PLR0912
        cls,
        out_of_date: list[FlatLayerToken],
        up_to_date: list[FlatLayerToken],
    ) -> tuple[list[FlatLayerToken], FlatLayerToken | None, FlatLayerToken | None]:
        if len([token for token in out_of_date if token.type == "target"]) != 1:
            message = "The out of date branch must contain exactly one target"
            raise ValueError(message)

        token_index, target = next((i, token) for i, token in enumerate(out_of_date) if token.type == "target")
        assert target.quuid is not None  # noqa: S101

        if any(token.type == "target" for token in up_to_date):
            message = "The up to date branch must not contain any target"
            raise ValueError(message)

        out_of_date_no_token = [token for token in out_of_date if token.type != "target"]

        matcher = difflib.SequenceMatcher(None, out_of_date_no_token, up_to_date)
        actions: list[FlatTokenAction] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                src_slice = out_of_date_no_token[i1:i2]
                dest_slice = up_to_date[j1:j2]

                common_len = min(len(src_slice), len(dest_slice))

                for k in range(common_len):
                    actions.append(FlatTokenAction(type="replace", token=dest_slice[k], index=i1 + k))

                if len(src_slice) > len(dest_slice):
                    for k in range(common_len, len(src_slice)):
                        actions.append(FlatTokenAction(type="delete", token=src_slice[k], index=i1 + k))

                elif len(dest_slice) > len(src_slice):
                    insertion_start = i1 + common_len
                    for k in range(common_len, len(dest_slice)):
                        actions.append(FlatTokenAction(type="create", token=dest_slice[k], index=insertion_start))

            elif tag == "delete":
                for k in range(i1, i2):
                    actions.append(FlatTokenAction(type="delete", token=out_of_date_no_token[k], index=k))

            elif tag == "insert":
                for k in range(j1, j2):
                    actions.append(FlatTokenAction(type="create", token=up_to_date[k], index=i1))

        rebased, token_index = cls._apply_actions(actions, out_of_date, token_index)

        parent = None
        parent_index = token_index
        level = 0
        while parent_index > 0:
            parent_index -= 1
            if rebased[parent_index].type == "group_start":
                level += 1
            elif rebased[parent_index].type == "group_end":
                level -= 1

            if level > 0:
                parent = rebased[parent_index]
                break

        sibling = None
        sibling_index = token_index - 1

        if sibling_index >= 0 and rebased[sibling_index].type != "group_start":
            sibling = rebased[sibling_index]

        return rebased, parent, sibling

    @staticmethod
    def _apply_actions(actions: list["FlatTokenAction"], tokens: list[FlatLayerToken], token_index: int) -> tuple[list[FlatLayerToken], int]:
        tokens = list(tokens)
        shift = 0

        for action in actions:
            current_action_index = action.index + shift

            if action.type == "replace":
                if current_action_index < token_index:
                    tokens[current_action_index] = action.token
                else:
                    tokens[current_action_index + 1] = action.token

                continue

            if current_action_index < token_index:
                if action.type == "create":
                    tokens.insert(current_action_index, action.token)
                    token_index += 1
                    shift += 1
                elif action.type == "delete":
                    tokens.pop(current_action_index)
                    token_index -= 1
                    shift -= 1
            else:
                actual_insertion_point = current_action_index + 1

                if action.type == "create":
                    tokens.insert(actual_insertion_point, action.token)
                    shift += 1
                elif action.type == "delete":
                    tokens.pop(actual_insertion_point)
                    shift -= 1

        return tokens, token_index


class FlatTokenAction(BaseModel):
    type: Literal["create", "delete", "replace"]
    token: FlatLayerToken
    index: int
