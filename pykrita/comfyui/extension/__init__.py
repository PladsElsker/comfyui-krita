from typing import cast

from krita import DockWidgetFactory, DockWidgetFactoryBase, Extension, Krita, Window

from comfyui.extension.comfy_krita_bridge import ComfyKritaBridge
from comfyui.extension.comfy_websocket import ComfyWebsocket
from comfyui.extension.config import Config
from comfyui.extension.document_monitor import DocumentMonitor
from comfyui.extension.ui.connection import ComfyUIWebsocketConnectionDialog
from comfyui.extension.ui.docker import COMFYUI_DOCKER_OBJECT_NAME, ComfyUIDocker


class ComfyUIExtension(Extension):
    def __init__(self, parent: Krita) -> None:
        super().__init__(parent)
        self.comfy_ws = ComfyWebsocket()
        self.document_monitor = DocumentMonitor()
        self.bridge = ComfyKritaBridge(self.comfy_ws, self.document_monitor)
        self.config = Config()

        ComfyUIWebsocketConnectionDialog(
            comfy_ws=self.comfy_ws,
            config=self.config,
        ).connect()

        self.docker_factory = DockWidgetFactory(
            "comfyui_docker",
            DockWidgetFactoryBase.DockPosition.DockRight,
            ComfyUIDocker,
        )
        Krita.instance().addDockWidgetFactory(self.docker_factory)

    @classmethod
    def get_comfyui_window_docker_pairs(cls) -> list[tuple[ComfyUIDocker, Window]]:
        pairs = []

        for window in Krita.instance().windows():
            for docker in window.dockers():
                if docker.objectName() != COMFYUI_DOCKER_OBJECT_NAME:
                    continue

                docker = cast("ComfyUIDocker", docker)
                pairs.append((docker, window))

        return pairs

    def setup(self) -> None:
        self.comfy_ws.enable_automatic_reconnection()
        self.document_monitor.on_documents_changed.connect(self.bridge.update_documents)
        self.document_monitor.on_active_document_changed.connect(self.broadcast_active_document_changed_to_comfy_dockers)

    def createActions(self, window: Window) -> None:  # noqa: N802
        action = window.createAction(
            "ComfyUISetup-15347",
            "ComfyUI...",
            "settings",
        )
        action.triggered.connect(self.open_config)

    def open_config(self) -> None:
        dialog = ComfyUIWebsocketConnectionDialog(comfy_ws=self.comfy_ws, config=self.config)
        dialog.exec_()

    def broadcast_active_document_changed_to_comfy_dockers(self) -> None:
        for docker, window in ComfyUIExtension.get_comfyui_window_docker_pairs():
            active_view = window.activeView()

            if active_view is None:
                continue

            active_document = active_view.document()

            if active_document is None:
                continue

            docker.set_active_document(active_document)
