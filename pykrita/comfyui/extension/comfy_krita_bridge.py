import json
from contextlib import suppress
import logging
import threading
from io import BytesIO
from zipfile import ZIP_STORED, ZipFile

from PyQt5.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    QTimer,
    Qt,
    pyqtSignal,
    pyqtSlot,
)

from comfyui.extension.comfy_websocket import ComfyWebsocket
from comfyui.extension.document_monitor import DocumentMonitor
from comfyui.extension.image_import import insert_png_image
from comfyui.extension.models import (
    DocumentMappingResponse,
    LayerCreateNotification,
    LoadImageState,
    SaveImageState,
    StatusRequest,
    UpdateDocumentsRequest,
    UpdateWorkflowsRequest,
)

LOGGER = logging.getLogger(__name__)
MAX_NODE_STATE_UPLOAD_ATTEMPTS = 3


def _extract_load_image_snapshot_revision(response: str) -> str:
    upload_result = json.loads(response)
    snapshot_revision = upload_result.get("snapshot_revision")
    if not isinstance(snapshot_revision, str) or not snapshot_revision:
        message = "ComfyUI did not return the canonical Load Image snapshot revision"
        raise RuntimeError(message)
    return snapshot_revision


class _NodeStateUploadTask(QRunnable):
    def __init__(self, bridge: "ComfyKritaBridge") -> None:
        super().__init__()
        self.bridge = bridge

    def run(self) -> None:
        self.bridge.drain_node_state_updates()


class _ImageDownloadSignals(QObject):
    completed = pyqtSignal(object, bytes)
    failed = pyqtSignal(object, str)


class _ImageDownloadTask(QRunnable):
    def __init__(
        self,
        comfy_ws: ComfyWebsocket,
        notification: LayerCreateNotification,
    ) -> None:
        super().__init__()
        self.comfy_ws = comfy_ws
        self.notification = notification
        self.signals = _ImageDownloadSignals()

    def run(self) -> None:
        transfer_id = self.notification.transfer_id
        route = f"/krita/images/{transfer_id}"
        try:
            image_data = self.comfy_ws.get_bytes(route)
        except Exception as error:  # noqa: BLE001
            self.signals.failed.emit(self.notification, str(error))
            return

        self.signals.completed.emit(self.notification, image_data)


class _LoadImageUploadSignals(QObject):
    completed = pyqtSignal(object, object, bytes, str)
    failed = pyqtSignal(object, object, str)


class _LoadImageUploadTask(QRunnable):
    def __init__(
        self,
        comfy_ws: ComfyWebsocket,
        sid: str,
        widget: object,
        state: LoadImageState,
        image_data: bytes,
    ) -> None:
        super().__init__()
        self.comfy_ws = comfy_ws
        self.sid = sid
        self.widget = widget
        self.state = state
        self.image_data = image_data
        self.signals = _LoadImageUploadSignals()

    def run(self) -> None:
        package_buffer = BytesIO()
        try:
            with ZipFile(package_buffer, "w", compression=ZIP_STORED) as archive:
                archive.writestr("state.json", self.state.model_dump_json())
                archive.writestr("composite.png", self.image_data)
            response = self.comfy_ws.put_bytes(
                f"/krita/{self.sid}/nodes/load-image",
                package_buffer.getvalue(),
                content_type="application/zip",
            )
            snapshot_revision = _extract_load_image_snapshot_revision(response)
        except Exception as error:  # noqa: BLE001
            self.signals.failed.emit(self.widget, self.state, str(error))
            return

        self.signals.completed.emit(
            self.widget,
            self.state,
            self.image_data,
            snapshot_revision,
        )


class ComfyKritaBridge(QObject):
    _state_upload_retry_requested = pyqtSignal()

    def __init__(
        self,
        comfy_ws: ComfyWebsocket,
        document_monitor: DocumentMonitor,
    ) -> None:
        super().__init__()
        self.comfy_ws = comfy_ws
        self.document_monitor = document_monitor
        self._connected_node_lists: set[int] = set()
        self._image_downloads: dict[str, _ImageDownloadTask] = {}
        self._load_image_snapshots: dict[
            tuple[str, int, str],
            tuple[LoadImageState, bytes],
        ] = {}
        self._pending_load_image_snapshots: dict[
            tuple[str, int, str],
            tuple[object, LoadImageState, bytes],
        ] = {}
        self._active_load_image_snapshot_uploads: dict[
            tuple[str, int, str],
            _LoadImageUploadTask,
        ] = {}
        self._load_image_upload_attempts: dict[tuple[str, int, str, str], int] = {}

        self._download_pool = QThreadPool(self)
        self._download_pool.setMaxThreadCount(1)
        self._load_image_upload_pool = QThreadPool(self)
        self._load_image_upload_pool.setMaxThreadCount(1)

        # Node-state HTTP writes are serialized on one worker. Coalescing by
        # document/node/type means only the newest pending value is sent.
        self._state_upload_pool = QThreadPool(self)
        self._state_upload_pool.setMaxThreadCount(1)
        self._pending_node_state_updates: dict[tuple[str, int, str], dict] = {}
        self._node_state_upload_running = False
        self._node_state_upload_lock = threading.Lock()
        self._node_state_upload_attempts: dict[tuple[str, int, str], int] = {}
        self._state_upload_retry_requested.connect(
            self._schedule_node_state_upload_retry,
            Qt.ConnectionType.QueuedConnection,
        )
        self._define_commands()

    def _define_commands(self) -> None:
        @self.comfy_ws.handler("status")
        def status_statement(data: dict) -> None:
            try:
                status_request = StatusRequest.model_validate(data)
                self.status_statement(status_request)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Could not register the Krita websocket session with ComfyUI")

        @self.comfy_ws.handler("krita::workflows::update")
        def update_workflows(data: dict) -> None:
            workflows_request = UpdateWorkflowsRequest.model_validate(data)
            self.update_workflows(workflows_request)

        @self.comfy_ws.handler("krita::layers::create")
        def create_layer(data: dict) -> None:
            try:
                notification = LayerCreateNotification.model_validate(data)
                self._download_layer_image(notification)
            except Exception as error:  # noqa: BLE001
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
        update_request = UpdateDocumentsRequest(
            documents=documents,
            previous_mappings=self.document_monitor.document_id_mapping,
        )
        response = self.comfy_ws.put(
            f"/krita/{sid}/documents",
            update_request.model_dump(),
        )
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
                node_list.snapshot_upload_requested.connect(self._queue_load_image_snapshot_upload)
                self._connected_node_lists.add(node_list_id)

            docker.update_title(workflows_request.name, found_document_id)
            docker.update_node_list(
                found_nodes,
                window,
                active_document,
                found_document_id,
            )
            docker.set_active_document(window, active_document, found_document_id)

    def send_krita_state(self) -> None:
        if not self.comfy_ws.is_connected or self.comfy_ws.sid is None:
            return

        from . import ComfyUIExtension  # noqa: PLC0415

        for docker, _window in ComfyUIExtension.get_comfyui_window_docker_pairs():
            node_list = docker.node_list
            node_list_id = id(node_list)
            if node_list_id not in self._connected_node_lists:
                node_list.node_state_changed.connect(self._publish_node_state)
                node_list.snapshot_upload_requested.connect(self._queue_load_image_snapshot_upload)
                self._connected_node_lists.add(node_list_id)

            for state in node_list.previous_node_states.values():
                if isinstance(state, SaveImageState):
                    self._send_save_image_state(state)
                elif isinstance(state, LoadImageState):
                    key = (state.document_id, state.id, state.type)
                    pending = self._pending_load_image_snapshots.get(key)
                    if pending is not None and pending[1].snapshot_revision == state.snapshot_revision:
                        continue

                    cached = self._load_image_snapshots.get(key)
                    if cached is not None and cached[0].snapshot_revision == state.snapshot_revision and state.snapshot_revision:
                        self._queue_load_image_snapshot_upload(None, state, cached[1])
                    elif not state.snapshot_revision:
                        self._publish_node_state({"deleted": False, "state": state})

        # Also flush tombstones, image snapshots, and state updates that
        # accumulated while disconnected.
        self._start_pending_load_image_snapshot_uploads()
        self._start_pending_node_state_upload()

    def _publish_node_state(self, update: dict) -> None:
        if update.get("deleted", False):
            document_id = update.get("document_id")
            node_id = update.get("id")
            node_type = update.get("type")
            if not isinstance(document_id, str) or not isinstance(node_id, int) or not isinstance(node_type, str):
                LOGGER.warning("Ignoring an incomplete deleted Krita node-state update")
                return
            key = (document_id, node_id, node_type)
            self._load_image_snapshots.pop(key, None)
            self._pending_load_image_snapshots.pop(key, None)
            payload = {
                "deleted": True,
                "document_id": document_id,
                "id": node_id,
                "type": node_type,
            }
        else:
            state = update.get("state")
            if isinstance(state, SaveImageState):
                key = (state.document_id, state.id, state.type)
                serialized_state = self._serialize_save_image_state(state)
            elif isinstance(state, LoadImageState):
                key = (state.document_id, state.id, state.type)
                serialized_state = state.model_dump()
                if not state.layer_ids or not state.snapshot_revision:
                    self._load_image_snapshots.pop(key, None)
                    self._pending_load_image_snapshots.pop(key, None)
            else:
                return
            payload = {"deleted": False, "state": serialized_state}

        # Keep updates even while disconnected. On reconnect the status flow
        # refreshes the document mapping and calls send_krita_state().
        with self._node_state_upload_lock:
            self._pending_node_state_updates[key] = payload
            self._node_state_upload_attempts.pop(key, None)

        self._start_pending_node_state_upload()

    def _queue_load_image_snapshot_upload(
        self,
        widget: object,
        state: LoadImageState,
        image_data: bytes,
    ) -> None:
        key = (state.document_id, state.id, state.type)
        previous = self._pending_load_image_snapshots.get(key)
        if previous is None or previous[1].snapshot_revision != state.snapshot_revision:
            self._load_image_upload_attempts.pop((*key, state.snapshot_revision), None)
        self._pending_load_image_snapshots[key] = (widget, state, image_data)
        self._start_pending_load_image_snapshot_uploads()

    def _start_pending_load_image_snapshot_uploads(self) -> None:
        sid = self.comfy_ws.sid
        if sid is None or not self.comfy_ws.is_connected:
            return

        for key, (widget, state, image_data) in list(self._pending_load_image_snapshots.items()):
            if key in self._active_load_image_snapshot_uploads:
                continue
            attempts_key = (*key, state.snapshot_revision)
            if self._load_image_upload_attempts.get(attempts_key, 0) >= MAX_NODE_STATE_UPLOAD_ATTEMPTS:
                continue

            task = _LoadImageUploadTask(self.comfy_ws, sid, widget, state, image_data)
            task.signals.completed.connect(
                self._on_load_image_snapshot_uploaded,
                Qt.ConnectionType.QueuedConnection,
            )
            task.signals.failed.connect(
                self._on_load_image_snapshot_upload_failed,
                Qt.ConnectionType.QueuedConnection,
            )
            self._active_load_image_snapshot_uploads[key] = task
            self._load_image_upload_pool.start(task)

    @pyqtSlot(object, object, bytes, str)
    def _on_load_image_snapshot_uploaded(
        self,
        widget: object,
        state: LoadImageState,
        image_data: bytes,
        snapshot_revision: str,
    ) -> None:
        key = (state.document_id, state.id, state.type)
        self._active_load_image_snapshot_uploads.pop(key, None)
        pending = self._pending_load_image_snapshots.get(key)
        if pending is None or pending[1].snapshot_revision != state.snapshot_revision:
            self._start_pending_load_image_snapshot_uploads()
            return

        self._pending_load_image_snapshots.pop(key, None)
        canonical_state = state.model_copy(update={"snapshot_revision": snapshot_revision})
        self._load_image_snapshots[key] = (canonical_state, image_data)
        self._load_image_upload_attempts.pop((*key, state.snapshot_revision), None)
        if widget is not None and hasattr(widget, "snapshot_uploaded"):
            with suppress(RuntimeError):
                # The backend revision is derived from normalized RGBA pixels
                # and is the execution-cache identity used by ComfyUI.
                widget.snapshot_uploaded(canonical_state)

        self._start_pending_load_image_snapshot_uploads()

    @pyqtSlot(object, object, str)
    def _on_load_image_snapshot_upload_failed(
        self,
        widget: object,
        state: LoadImageState,
        error: str,
    ) -> None:
        key = (state.document_id, state.id, state.type)
        self._active_load_image_snapshot_uploads.pop(key, None)
        attempts_key = (*key, state.snapshot_revision)
        attempts = self._load_image_upload_attempts.get(attempts_key, 0) + 1
        self._load_image_upload_attempts[attempts_key] = attempts
        LOGGER.error(
            "Could not upload Krita input snapshot for node %s: %s",
            state.id,
            error,
        )
        if attempts < MAX_NODE_STATE_UPLOAD_ATTEMPTS:
            QTimer.singleShot(1000, self._start_pending_load_image_snapshot_uploads)
        elif widget is not None and hasattr(widget, "snapshot_upload_failed"):
            with suppress(RuntimeError):
                widget.snapshot_upload_failed(state, error)

    def _start_pending_node_state_upload(self) -> None:
        with self._node_state_upload_lock:
            if self._node_state_upload_running or not self._pending_node_state_updates:
                return
            if self.comfy_ws.sid is None or not self.comfy_ws.is_connected:
                return
            self._node_state_upload_running = True

        self._state_upload_pool.start(_NodeStateUploadTask(self))

    def drain_node_state_updates(self) -> None:
        while True:
            batch = self._take_pending_node_state_batch()
            if not batch:
                return

            for index, (key, payload) in enumerate(batch):
                sid = self.comfy_ws.sid
                if sid is None or not self.comfy_ws.is_connected:
                    self._requeue_unsent_node_state_updates(batch[index:])
                    return

                if not self._upload_node_state(sid, payload):
                    self._retry_unsent_node_state_updates(batch[index:])
                    return

                with self._node_state_upload_lock:
                    self._node_state_upload_attempts.pop(key, None)

    def _take_pending_node_state_batch(self) -> list[tuple[tuple[str, int, str], dict]]:
        with self._node_state_upload_lock:
            if not self._pending_node_state_updates:
                self._node_state_upload_running = False
                return []
            batch = list(self._pending_node_state_updates.items())
            self._pending_node_state_updates.clear()
            return batch

    def _requeue_unsent_node_state_updates(
        self,
        updates: list[tuple[tuple[str, int, str], dict]],
    ) -> None:
        with self._node_state_upload_lock:
            for key, payload in updates:
                self._pending_node_state_updates.setdefault(key, payload)
            self._node_state_upload_running = False

    def _upload_node_state(self, sid: str, payload: dict) -> bool:
        try:
            self.comfy_ws.put(f"/krita/{sid}/nodes/state", payload)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Could not synchronize Krita output-node state with ComfyUI")
            return False
        return True

    def _retry_unsent_node_state_updates(
        self,
        updates: list[tuple[tuple[str, int, str], dict]],
    ) -> None:
        with self._node_state_upload_lock:
            for key, payload in updates:
                if key in self._pending_node_state_updates:
                    continue
                attempts = self._node_state_upload_attempts.get(key, 0) + 1
                self._node_state_upload_attempts[key] = attempts
                if attempts <= MAX_NODE_STATE_UPLOAD_ATTEMPTS:
                    self._pending_node_state_updates[key] = payload
            self._node_state_upload_running = False
            should_retry = bool(self._pending_node_state_updates)

        if should_retry:
            self._state_upload_retry_requested.emit()

    @pyqtSlot()
    def _schedule_node_state_upload_retry(self) -> None:
        QTimer.singleShot(500, self._start_pending_node_state_upload)
        QTimer.singleShot(500, self._start_pending_load_image_snapshot_uploads)

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
        if notification.transfer_id in self._image_downloads:
            LOGGER.warning(
                "Ignoring duplicate generated image transfer %s",
                notification.transfer_id,
            )
            return

        task = _ImageDownloadTask(self.comfy_ws, notification)
        task.signals.completed.connect(
            self._on_image_downloaded,
            Qt.ConnectionType.QueuedConnection,
        )
        task.signals.failed.connect(
            self._on_image_download_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        self._image_downloads[notification.transfer_id] = task
        self._download_pool.start(task)

    @pyqtSlot(object, bytes)
    def _on_image_downloaded(
        self,
        notification: LayerCreateNotification,
        image_data: bytes,
    ) -> None:
        self._image_downloads.pop(notification.transfer_id, None)
        state = notification.state

        opened_documents = self.document_monitor.get_opened_documents()
        document = self.document_monitor.mapping.get(state.document_id)
        if document is None:
            LOGGER.error(
                "Fetched generated image %s (%d bytes), but " "Krita has no document mapping for ID %s",
                notification.transfer_id,
                len(image_data),
                state.document_id,
            )
            return

        if document not in opened_documents:
            LOGGER.error(
                "Fetched generated image %s (%d bytes), but " "target document %s is not open",
                notification.transfer_id,
                len(image_data),
                state.document_id,
            )
            return

        layer_name = f"ComfyUI Output {state.id}"
        if notification.batch_size > 1:
            layer_name += f" ({notification.batch_index + 1}/{notification.batch_size})"

        try:
            insert_png_image(document, image_data, state.path, layer_name)
        except Exception as error:  # noqa: BLE001
            LOGGER.exception(
                "Generated image %s was fetched but could not be " "inserted into document %s",
                notification.transfer_id,
                state.document_id,
            )
            return

    @pyqtSlot(object, str)
    def _on_image_download_failed(
        self,
        notification: LayerCreateNotification,
        error: str,
    ) -> None:
        self._image_downloads.pop(notification.transfer_id, None)
        LOGGER.error(
            "Could not download generated image %s: %s",
            notification.transfer_id,
            error,
        )
