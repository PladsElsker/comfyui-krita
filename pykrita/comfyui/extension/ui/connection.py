from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..comfy_websocket import ComfyWebsocket  # noqa: TID252
from ..config import Config  # noqa: TID252

SUCCESS_COLOR_STYLE = "color: rgb(69, 255, 81);"
ERROR_COLOR_STYLE = "color: rgb(255, 69, 69);"
DEFAULT_COLOR_STYLE = "color: rgb(255, 255, 255);"
DEFAULT_SERVER_URL = "http://127.0.0.1:8188"
COMFYUI_SERVER_URL_CONFIG = "comfyui-server-url"


class ComfyUIWebsocketConnectionDialog(QDialog):
    def __init__(self, comfy_ws: ComfyWebsocket, config: Config, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)

        self.config = config
        server_url = config.get(COMFYUI_SERVER_URL_CONFIG, DEFAULT_SERVER_URL)

        self.comfy_ws = comfy_ws
        comfy_ws.on_open.connect(self._on_ws_connected)
        comfy_ws.on_closed.connect(self._on_ws_disconnected)
        comfy_ws.on_reconnect.connect(self._on_ws_reconnect)

        self.setWindowTitle("ComfyUI Setup")
        self.setModal(True)
        self.resize(400, 150)

        self.url_edit = QLineEdit(self)
        self.url_edit.setText(server_url)

        self.status_label = QLabel("", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)

        self.connect_button = QPushButton("Connect", self)
        close_button = QPushButton("Close", self)

        self.connect_button.clicked.connect(self.connect)
        close_button.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("ComfyUI Server URL:", self))
        layout.addWidget(self.url_edit)
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        button_row.addWidget(self.connect_button)
        button_row.addStretch(1)
        button_row.addWidget(close_button)

        layout.addLayout(button_row)
        self.setLayout(layout)

        if comfy_ws.is_connected:
            self._on_ws_connected()
        else:
            self._on_ws_disconnected()

    def connect(self) -> None:
        if self.comfy_ws.is_connected:
            self.comfy_ws.close()
            self.comfy_ws.disable_automatic_reconnection()
        else:
            self.connect_button.setText("Connecting...")
            self.connect_button.setDisabled(True)
            url = self.url_edit.text().strip()
            self.config[COMFYUI_SERVER_URL_CONFIG] = url
            self.comfy_ws.connect(url)
            self.comfy_ws.enable_automatic_reconnection()

    def _on_ws_connected(self) -> None:
        self.connect_button.setText("Disconnect")
        self.connect_button.setEnabled(True)
        self.status_label.setText("Connected")
        self.status_label.setStyleSheet(SUCCESS_COLOR_STYLE)
        self.url_edit.setDisabled(True)

    def _on_ws_disconnected(self) -> None:
        self.connect_button.setText("Connect")
        self.connect_button.setEnabled(True)
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet(ERROR_COLOR_STYLE)
        self.url_edit.setEnabled(True)

    def _on_ws_reconnect(self) -> None:
        self.connect_button.setText("Cancel")
        self.connect_button.setEnabled(True)
        self.status_label.setText("Connecting...")
        self.status_label.setStyleSheet(DEFAULT_COLOR_STYLE)
        self.url_edit.setEnabled(True)
