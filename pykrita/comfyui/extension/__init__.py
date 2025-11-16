from krita import Extension, DockWidgetFactory, DockWidgetFactoryBase, Krita
from typing import cast

from .config import Config
from .comfy_websocket import ComfyWebsocket
from .comfy_krita_bridge import ComfyKritaBridge
from .document_monitor import DocumentMonitor
from .ui.connection import ComfyUIWebsocketConnectionDialog
from .ui.docker import ComfyUIDocker, COMFYUI_DOCKER_OBJECT_NAME


class ComfyUIExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.comfy_ws = ComfyWebsocket()
        self.document_monitor = DocumentMonitor()
        self.bridge = ComfyKritaBridge(self.comfy_ws, self.document_monitor)
        self.config = Config()

        ComfyUIWebsocketConnectionDialog(
            comfy_ws=self.comfy_ws, 
            config=self.config
        ).connect()

        self.docker_factory = DockWidgetFactory(
            "comfyui_docker",
            DockWidgetFactoryBase.DockPosition.DockRight,
            ComfyUIDocker
        )
        Krita.instance().addDockWidgetFactory(self.docker_factory)

    @classmethod
    def get_comfyui_dockers(cls) -> list[ComfyUIDocker]:
        dockers = []

        for window in Krita.instance().windows():
            for docker in window.dockers():
                if docker.objectName() != COMFYUI_DOCKER_OBJECT_NAME:
                    continue

                docker = cast(ComfyUIDocker, docker)
                dockers.append(docker)

        return dockers

    def setup(self):
        self.comfy_ws.enable_automatic_reconnection()
        self.document_monitor.on_documents_changed.connect(self.bridge.update_documents)
        self.document_monitor.on_active_document_changed.connect(self.broadcast_active_document_changed_to_comfy_dockers)

    def createActions(self, window):
        action = window.createAction(
            "ComfyUISetup-15347", "ComfyUI...", "settings", 
        )
        action.triggered.connect(self.open_config)

    def open_config(self):
        dialog = ComfyUIWebsocketConnectionDialog(comfy_ws=self.comfy_ws, config=self.config)
        dialog.exec_()

    def broadcast_active_document_changed_to_comfy_dockers(self, document_id: str) -> None:
        for docker in ComfyUIExtension.get_comfyui_dockers():
            docker.set_active_document(document_id)
