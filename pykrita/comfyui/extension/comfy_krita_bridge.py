import contextlib
import json
import logging

from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot

from comfyui.extension.comfy_websocket import ComfyWebsocket
from comfyui.extension.document_monitor import DocumentMonitor
from comfyui.extension.image_import import insert_png_image
from comfyui.extension.models import (
    DocumentMappingResponse,
    LayerCreateNotification,
    SaveImageState,
    StatusRequest,
    UpdateDocumentsRequest,
    UpdateWorkflowsRequest,
)

LOGGER = logging.getLogger(__name__)


class _ImageDownloadSignals(QObject):
    completed = pyqtSignal(object, bytes)
    failed = pyqtSignal(object, str)


class _ImageDownloadTask(QRunnable):
    def __init__(self, comfy_ws: ComfyWebsocket, sid: str, notification: LayerCreateNotification) -> None:
        super().__init__()
        self.comfy_ws = comfy_ws
        self.sid = sid
        self.notification = notification
        self.signals = _ImageDownloadSignals()

    def run(self) -> None:
        try:
            route = f"/krita/{self.sid}/images/{self.notification.transfer_id}"
            image_data = self.comfy_ws.get_bytes(route)
        except Exception as error:  # noqa: BLE001
            self.signals.failed.emit(self.notification, str(error))
            return

        self.signals.completed.emit(self.notification, image_data)


class ComfyKritaBridge(QObject):
    def __init__(self, comfy_ws: ComfyWebsocket, document_monitor: DocumentMonitor) -> None:
        super().__init__()
        self.comfy_ws = comfy_ws
        self.document_monitor = document_monitor
        self._connected_node_lists: set[int] = set()
        self._image_downloads: dict[str, _ImageDownloadTask] = {}
        self._download_pool = QThreadPool.globalInstance()
        self._define_commands()

    def _define_commands(self) -> None:
        @self.comfy_ws.handler("status")
        def status_statement(data: dict) -> None:
            with contextlib.suppress(Exception):
                status_request = StatusRequest.model_validate(data)
                self.status_statement(status_request)

        @self.comfy_ws.handler("krita::workflows::update")
        def update_workflows(data: dict) -> None:
            workflows_request = UpdateWorkflowsRequest.model_validate(data)
            self.update_workflows(workflows_request)

        @self.comfy_ws.handler("krita::layers::create")
        def create_layer(data: dict) -> None:
            try:
                notification = LayerCreateNotification.model_validate(data)
                self._download_layer_image(notification)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Received an invalid generated-layer notification")

    def status_statement(self, status_request: StatusRequest) -> None:
        self.comfy_ws.sid = status_request.sid
        self.update_documents()

    def update_documents(self) -> None:
        if not self.comfy_ws.is_connected:
            return

        mappings = self.generate_document_name_mappings()

        if not self.document_monitor.test_mappings(mappings):
            mappings = self.generate_document_name_mappings()

        self.document_monitor.assign_name_mappings(mappings)
        self.request_workflows()
        self.send_krita_state()

    def request_workflows(self) -> None:
        if self.comfy_ws.sid is None:
            message = "The sid is not defined"
            raise ValueError(message)

        data = self.comfy_ws.get(f"krita/{self.comfy_ws.sid}/workflows")

        # None is allowed, no workflows for our sid
        if json.loads(data) is None:
            return

        workflows_request = UpdateWorkflowsRequest.model_validate_json(data)
        self.update_workflows(workflows_request)

    def generate_document_name_mappings(self) -> dict[str, str]:
        if self.comfy_ws.sid is None:
            message = "The sid is not defined"
            raise ValueError(message)

        sid = self.comfy_ws.sid
        documents = [doc.name() for doc in self.document_monitor.get_opened_documents()]
        update_request = UpdateDocumentsRequest(documents=documents, previous_mappings=self.document_monitor.document_id_mapping)
        response = self.comfy_ws.put(f"/krita/{sid}/documents", update_request.model_dump())
        return DocumentMappingResponse.model_validate_json(response).mapping

    def update_workflows(self, workflows_request: UpdateWorkflowsRequest) -> None:
        from . import ComfyUIExtension  # noqa: PLC0415

        for docker, window in ComfyUIExtension.get_comfyui_window_docker_pairs():
            active_view = window.activeView()
            if active_view is None:
                continue

            active_document = active_view.document()
            if active_document is None:
                continue

            found_document_id = None
            found_nodes = None

            for document_id, nodes in workflows_request.workflows.items():
                document = self.document_monitor.mapping.get(document_id, None)

                if document != active_document:
                    continue

                found_document_id = document_id
                found_nodes = nodes

            if found_document_id is None or found_nodes is None:
                continue

            node_list = docker.node_list
            node_list_id = id(node_list)
            if node_list_id not in self._connected_node_lists:
                node_list.node_state_changed.connect(self._publish_node_state)
                self._connected_node_lists.add(node_list_id)

            docker.update_title(workflows_request.name, found_document_id)
            docker.update_node_list(found_nodes, window, active_document, found_document_id)

    def send_krita_state(self) -> None:
        if not self.comfy_ws.is_connected or self.comfy_ws.sid is None:
            return

        from . import ComfyUIExtension  # noqa: PLC0415

        for docker, _window in ComfyUIExtension.get_comfyui_window_docker_pairs():
            node_list = docker.node_list
            node_list_id = id(node_list)
            if node_list_id not in self._connected_node_lists:
                node_list.node_state_changed.connect(self._publish_node_state)
                self._connected_node_lists.add(node_list_id)

            for state in node_list.previous_node_states.values():
                if isinstance(state, SaveImageState):
                    self._send_save_image_state(state)

    def _publish_node_state(self, update: dict) -> None:
        if self.comfy_ws.sid is None or not self.comfy_ws.is_connected:
            return

        if update.get("deleted", False):
            payload = {
                "deleted": True,
                "document_id": update["document_id"],
                "id": update["id"],
                "type": update["type"],
            }
        else:
            state = update.get("state")
            if not isinstance(state, SaveImageState):
                return
            payload = {"deleted": False, "state": self._serialize_save_image_state(state)}

        try:
            self.comfy_ws.put(f"/krita/{self.comfy_ws.sid}/nodes/state", payload)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Could not synchronize Krita output-node state with ComfyUI")

    def _send_save_image_state(self, state: SaveImageState) -> None:
        self._publish_node_state({"deleted": False, "state": state})

    @staticmethod
    def _serialize_save_image_state(state: SaveImageState) -> dict:
        return {
            "id": state.id,
            "type": state.type,
            "document_id": state.document_id,
            "insert_direction": state.insert_direction,
            "layer_name": state.layer_name,
            "path": [
                {
                    "quuid": str(token.quuid) if token.quuid is not None else None,
                    "type": token.type,
                }
                for token in state.path
            ],
        }

    def _download_layer_image(self, notification: LayerCreateNotification) -> None:
        sid = self.comfy_ws.sid
        if sid is None:
            LOGGER.warning("Ignoring generated image notification because the Krita session is not registered")
            return

        if notification.transfer_id in self._image_downloads:
            LOGGER.warning("Ignoring duplicate generated image transfer %s", notification.transfer_id)
            return

        task = _ImageDownloadTask(self.comfy_ws, sid, notification)
        task.signals.completed.connect(self._on_image_downloaded)
        task.signals.failed.connect(self._on_image_download_failed)
        self._image_downloads[notification.transfer_id] = task
        self._download_pool.start(task)

    @pyqtSlot(object, bytes)
    def _on_image_downloaded(self, notification: LayerCreateNotification, image_data: bytes) -> None:
        self._image_downloads.pop(notification.transfer_id, None)
        state = notification.state
        document = self.document_monitor.mapping.get(state.document_id)

        if document is None or document not in self.document_monitor.get_opened_documents():
            LOGGER.warning("Cannot insert generated image: Krita document %s is no longer open", state.document_id)
            return

        layer_name = f"ComfyUI Output {state.id}"
        if notification.batch_size > 1:
            layer_name += f" ({notification.batch_index + 1}/{notification.batch_size})"

        try:
            insert_png_image(document, image_data, state.path, layer_name)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Could not insert generated image for Krita node %s", state.id)

    @pyqtSlot(object, str)
    def _on_image_download_failed(self, notification: LayerCreateNotification, error: str) -> None:
        self._image_downloads.pop(notification.transfer_id, None)
        LOGGER.error("Could not download generated image %s: %s", notification.transfer_id, error)
