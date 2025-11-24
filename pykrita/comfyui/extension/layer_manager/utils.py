import difflib
from dataclasses import dataclass
from typing import Literal, cast

from krita import Node
from pydantic import BaseModel

from ..models import FlatLayerToken, KritaLayerType


class LayerUtils:
    @staticmethod
    def flatten_tree(roots: list[Node]) -> list[Node]:
        remaining = list(reversed(roots))
        flat_list = []

        while len(remaining) > 0:
            node = remaining.pop()

            if node is None:
                continue

            flat_list.append(node)
            node_type = cast("KritaLayerType", node.type())
            if node_type == "grouplayer":
                children = [n for n in reversed(node.childNodes()) if isinstance(n, Node)]
                remaining += children

        return flat_list

    @classmethod
    def to_flat_tokens(cls, roots: list[Node]) -> list[FlatLayerToken]:
        result: list[FlatLayerToken] = []

        for node in roots:
            if node is None:
                continue

            node_children = node.childNodes()
            is_parent = len(node_children) > 0 and cast("KritaLayerType", node.type()) == "grouplayer"
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


@dataclass
class LayerRelativePath:
    parent: Node
    sibling: Node | None
