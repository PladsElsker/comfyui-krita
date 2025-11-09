import json
import threading
import requests
import websocket
from urllib.parse import urlparse, urlunparse
from PyQt5.QtCore import QObject, pyqtSignal, pyqtBoundSignal, QMetaObject, Qt, pyqtSlot, Q_ARG, qCritical, QCoreApplication
from typing import cast
import atexit
import signal


class ComfyWebsocket(QObject):
    on_open = cast(pyqtBoundSignal, pyqtSignal(str))
    on_message = cast(pyqtBoundSignal, pyqtSignal(str))
    on_error = cast(pyqtBoundSignal, pyqtSignal(str))
    on_reconnect = cast(pyqtBoundSignal, pyqtSignal())
    on_closed = cast(pyqtBoundSignal, pyqtSignal(str))

    def __init__(self) -> None:
        super().__init__()
        self.ws = None
        self._listener_thread = None
        self.is_connected = False
        self._handlers = {}
        self.sid: str | None = None
        self._setup_graceful_termination()

    def connect(self, http_url: str) -> None:
        if self.ws is not None:
            self.ws.close()

        self._set_url(http_url)

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_reconnect=self._on_reconnect,
            on_close=self._on_close,
        )
        self._listener_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self._listener_thread.start()

    def close(self):
        if self.ws is not None:
            self.ws.close()

    def handler(self, command):
        def decorator(func):
            self._handlers[command] = func
            return func

        return decorator

    def get(self, route, **kw):
        return self._request("GET", route, **kw)

    def post(self, route, data=None, **kw):
        return self._request("POST", route, data, **kw)

    def put(self, route, data=None, **kw):
        return self._request("PUT", route, data, **kw)

    def delete(self, route, **kw):
        return self._request("DELETE", route, **kw)

    def _set_url(self, http_url: str) -> None:
        if not http_url.startswith(("http://", "https://")):
            raise ValueError("Only HTTP(S) URLs are allowed")

        self.http_base = http_url.rstrip("/")
        self.ws_url = _http_to_ws_base(http_url)

    def _request(self, method: str, route: str, data=None, timeout=5):
        url = f"{self.http_base.rstrip('/')}/{route.lstrip('/')}"
        headers = {"Content-Type": "application/json"}
        payload = json.dumps(data) if data is not None else None
        resp = requests.request(method, url, data=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return resp.text

    def _on_open(self, ws):
        QMetaObject.invokeMethod(self, "_emit_open", Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def _emit_open(self):
        self.is_connected = True
        self.on_open.emit(self.ws_url)

    def _on_message(self, ws, message):
        QMetaObject.invokeMethod(self, "_emit_message", Qt.ConnectionType.QueuedConnection, Q_ARG(str, message))

    @pyqtSlot(str)
    def _emit_message(self, message: str):
        data = json.loads(message)
        command = data.get("type", None)
        if command in self._handlers.keys():
            try:
                self._handlers[command](data.get("data", {}))
            except Exception as exception:
                qCritical(str(exception))

        self.on_message.emit(message)

    def _on_error(self, ws, error):
        QMetaObject.invokeMethod(self, "_emit_error", Qt.ConnectionType.QueuedConnection, Q_ARG(str, str(error)))

    @pyqtSlot(str)
    def _emit_error(self, error):
        self.on_error.emit(error)

    def _on_reconnect(self, ws):
        QMetaObject.invokeMethod(self, "_emit_reconnect", Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def _emit_reconnect(self):
        self.on_reconnect.emit()

    def _on_close(self, ws, close_status_code, close_message):
        QMetaObject.invokeMethod(self, "_emit_close", Qt.ConnectionType.QueuedConnection, Q_ARG(str, f"Socket closed with status {close_status_code}: {close_message}"))

    @pyqtSlot(str)
    def _emit_close(self, message: str):
        self.is_connected = False
        self.on_closed.emit(message)

    def _setup_graceful_termination(self):
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.close)

        atexit.register(self.close)

        def handle(signum, frame):
            self.close()

        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGTERM, handle)


def _http_to_ws_base(http_url: str) -> str:
    parts = urlparse(http_url)
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunparse((scheme, parts.netloc, "/ws", "", "", ""))
