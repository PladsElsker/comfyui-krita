# ruff: noqa: S101
import asyncio
import importlib.util
import sys
import types
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_krita_load_image_api_tests"
PACKAGE = types.ModuleType(PACKAGE_NAME)
PACKAGE.__path__ = [str(REPOSITORY_ROOT)]
sys.modules.setdefault(PACKAGE_NAME, PACKAGE)

FAKE_SERVER = types.ModuleType("server")


class _PromptServer:
    class _Instance:
        def __init__(self) -> None:
            self.sockets = {"test-sid": object()}
            self.messages: list[tuple[str, dict]] = []

        async def send(self, event: str, data: dict, sid: str | None = None) -> None:
            self.messages.append((event, data))

    instance = _Instance()


FAKE_SERVER.PromptServer = _PromptServer
_ORIGINAL_SERVER_MODULE = sys.modules.get("server")
sys.modules["server"] = FAKE_SERVER

SPEC = importlib.util.spec_from_file_location(
    f"{PACKAGE_NAME}.krita_api",
    REPOSITORY_ROOT / "krita_api.py",
)
assert SPEC is not None and SPEC.loader is not None
KRITA_API_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = KRITA_API_MODULE
SPEC.loader.exec_module(KRITA_API_MODULE)
if _ORIGINAL_SERVER_MODULE is None:
    sys.modules.pop("server", None)
else:
    sys.modules["server"] = _ORIGINAL_SERVER_MODULE

MODELS_MODULE = sys.modules[f"{PACKAGE_NAME}.models"]
LoadImageState = MODELS_MODULE.LoadImageState


def _rgba_png() -> bytes:
    image = Image.new("RGBA", (2, 1), (20, 30, 40, 128))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _load_state(revision: str = "revision-1") -> LoadImageState:
    return MODELS_MODULE.LoadImageState(
        id=42,
        type="KritaLoadImage-15348",
        document_id="document-1",
        layer_ids=["layer-1", "layer-2"],
        layer_names=["Background", "Line Art"],
        snapshot_revision=revision,
    )


def test__given_valid_snapshot__when_storing__then_state_and_pixels_are_cached_together(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_prompt_server = _PromptServer()
    monkeypatch.setattr(KRITA_API_MODULE.PromptServer, "instance", fake_prompt_server.instance)

    api = KRITA_API_MODULE.KritaApi()
    api.registered_documents["test-sid"] = {"document-1"}
    api._last_workflows_request.workflows["document-1"] = [
        KRITA_API_MODULE.Node(id=42, type="KritaLoadImage-15348", name="Load Image")
    ]
    state = _load_state()
    image_data = _rgba_png()

    asyncio.run(api.store_load_image_snapshot("test-sid", state, image_data))

    assert api.has_load_image_snapshot(state)
    assert api.get_load_image_snapshot(state) == image_data
    assert api.get_node_states() == [state]
    assert fake_prompt_server.instance.messages == [
        ("krita::nodes::update", {"deleted": False, "state": state.model_dump()}),
    ]


def test__given_replacement_snapshot__when_storing__then_old_revision_is_invalidated(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_prompt_server = _PromptServer()
    monkeypatch.setattr(KRITA_API_MODULE.PromptServer, "instance", fake_prompt_server.instance)

    api = KRITA_API_MODULE.KritaApi()
    api.registered_documents["test-sid"] = {"document-1"}
    api._last_workflows_request.workflows["document-1"] = [
        KRITA_API_MODULE.Node(id=42, type="KritaLoadImage-15348", name="Load Image")
    ]
    old_state = _load_state("revision-1")
    new_state = _load_state("revision-2")
    asyncio.run(api.store_load_image_snapshot("test-sid", old_state, _rgba_png()))
    asyncio.run(api.store_load_image_snapshot("test-sid", new_state, _rgba_png()))

    assert not api.has_load_image_snapshot(old_state)
    assert api.has_load_image_snapshot(new_state)
    assert api.get_load_image_snapshot(new_state) is not None


def test__given_snapshot_for_an_unregistered_document__when_storing__then_rejects() -> None:
    api = KRITA_API_MODULE.KritaApi()
    api.registered_documents["test-sid"] = {"another-document"}

    with pytest.raises(ValueError, match="does not belong"):
        asyncio.run(api.store_load_image_snapshot("test-sid", _load_state(), _rgba_png()))


def test__given_unknown_session__when_storing__then_rejects() -> None:
    api = KRITA_API_MODULE.KritaApi()

    with pytest.raises(LookupError, match="not registered"):
        asyncio.run(api.store_load_image_snapshot("missing-sid", _load_state(), _rgba_png()))

def test__given_node_removed_from_active_workflow__when_uploading_snapshot__then_rejects() -> None:
    api = KRITA_API_MODULE.KritaApi()
    api.registered_documents["test-sid"] = {"document-1"}

    with pytest.raises(ValueError, match="no longer present"):
        asyncio.run(api.store_load_image_snapshot("test-sid", _load_state(), _rgba_png()))
