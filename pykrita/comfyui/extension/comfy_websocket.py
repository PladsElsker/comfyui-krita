import atexit
import json
import signal
import threading
from collections.abc import Callable
from http import HTTPStatus
from typing import cast
from urllib.parse import urlparse, urlunparse

import urllib3
import websocket
from krita import Krita
from PyQt5.QtCore import Q_ARG, QCoreApplication, QMetaObject, QObject, Qt, QTimer, pyqtBoundSignal, pyqtSignal, pyqtSlot
from websocket import WebSocketApp

WsDataType = dict | list | str | float | None


class ComfyWebsocket(QObject):
    on_open = cast("pyqtBoundSignal", pyqtSignal(str))
    on_message = cast("pyqtBoundSignal", pyqtSignal(str))
    on_error = cast("pyqtBoundSignal", pyqtSignal(str))
    on_reconnect = cast("pyqtBoundSignal", pyqtSignal())
    on_closed = cast("pyqtBoundSignal", pyqtSignal(str))

    def __init__(self) -> None:
        super().__init__()
        self.ws = None
        self.ws_url = None
        self.http_base = None
        self._listener_thread = None
        self.is_connected = False
        self._handlers = {}
        self.sid: str | None = None
        self._setup_graceful_termination()

        self._reconnect_timer = None
        self._http = urllib3.PoolManager()

    def enable_automatic_reconnection(self, attempt_every: int = 3000) -> None:
        if self._reconnect_timer is not None:
            self._reconnect_timer.stop()

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(attempt_every)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)
        self._reconnect_timer.start()

    def disable_automatic_reconnection(self) -> None:
        if self._reconnect_timer is not None:
            self._reconnect_timer.stop()
            self._reconnect_timer = None

    def connect(self, http_url: str) -> None:
        if self.ws is not None:
            self.ws.close()

        self._set_url(http_url)

        assert self.ws_url is not None  # noqa: S101

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

    def close(self) -> None:
        if self.ws is not None:
            self.ws.close()

    def handler(self, command: str) -> Callable:
        def decorator(func: Callable) -> Callable:
            self._handlers[command] = func
            return func

        return decorator

    def put(self, route: str, data: WsDataType = None) -> str:
        return self._request("PUT", route, data)

    def _attempt_reconnect(self) -> None:
        if not self.is_connected and self.http_base is not None:
            self.connect(self.http_base)

    def _set_url(self, http_url: str) -> None:
        if not http_url.startswith(("http://", "https://")):
            message = "Only HTTP(S) URLs are allowed"
            raise ValueError(message)

        self.http_base = http_url.rstrip("/")
        self.ws_url = _http_to_ws_base(http_url)

    def _request(self, method: str, route: str, data: WsDataType = None, timeout: float = 5) -> str:
        assert self.http_base is not None  # noqa: S101

        url = f"{self.http_base.rstrip('/')}/{route.lstrip('/')}"
        headers = {"Content-Type": "application/json"}

        payload = json.dumps(data).encode("utf-8") if data is not None else None

        resp = self._http.request(
            method=method,
            url=url,
            body=payload,
            headers=headers,
            timeout=urllib3.Timeout(total=timeout),
        )

        if resp.status >= HTTPStatus.BAD_REQUEST.value:
            message = f"HTTP {resp.status}: {resp.data.decode('utf-8', 'replace')}"
            raise RuntimeError(message)

        return resp.data.decode("utf-8")

    def _on_open(self, ws: WebSocketApp) -> None:  # noqa: ARG002
        QMetaObject.invokeMethod(self, "_emit_open", Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def _emit_open(self) -> None:
        self.is_connected = True
        self.on_open.emit(self.ws_url)

    def _on_message(self, ws: WebSocketApp, message: str) -> None:  # noqa: ARG002
        QMetaObject.invokeMethod(self, "_emit_message", Qt.ConnectionType.QueuedConnection, Q_ARG(str, message))

    @pyqtSlot(str)
    def _emit_message(self, message: str) -> None:
        data = json.loads(message)
        command = data.get("type", None)
        if command in self._handlers:
            self._handlers[command](data.get("data", {}))

        self.on_message.emit(message)

    def _on_error(self, ws: WebSocketApp, error: Exception) -> None:  # noqa: ARG002
        QMetaObject.invokeMethod(self, "_emit_error", Qt.ConnectionType.QueuedConnection, Q_ARG(str, str(error)))

    @pyqtSlot(str)
    def _emit_error(self, error: str) -> None:
        self.on_error.emit(error)

    def _on_reconnect(self, ws: WebSocketApp) -> None:  # noqa: ARG002
        QMetaObject.invokeMethod(self, "_emit_reconnect", Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def _emit_reconnect(self) -> None:
        self.on_reconnect.emit()

    def _on_close(self, ws: WebSocketApp, close_status_code: int, close_message: str) -> None:  # noqa: ARG002
        QMetaObject.invokeMethod(
            self,
            "_emit_close",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, f"Socket closed with status {close_status_code}: {close_message}"),
        )

    @pyqtSlot(str)
    def _emit_close(self, message: str) -> None:
        self.is_connected = False
        self.on_closed.emit(message)

    def _setup_graceful_termination(self) -> None:
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.close)

        notifier = Krita.instance().notifier()
        notifier.setActive(True)
        notifier.applicationClosing.connect(self.close)  # type: ignore

        atexit.register(self.close)

        def handle(*args, **kwargs) -> None:  # noqa: ANN002, ANN003, ARG001
            self.close()

        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGTERM, handle)


def _http_to_ws_base(http_url: str) -> str:
    parts = urlparse(http_url)
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunparse((scheme, parts.netloc, "/ws", "", "", ""))
