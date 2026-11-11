from collections.abc import Callable

from krita import Document, Window
from PyQt5.QtCore import QEvent, QObject, QTimer
from PyQt5.QtWidgets import QApplication, QWidget

CHANGE_DEBOUNCE_MS = 450
_INPUT_EVENTS = {
    QEvent.Type.MouseButtonRelease,
    QEvent.Type.TabletRelease,
    QEvent.Type.TouchEnd,
    QEvent.Type.KeyRelease,
    QEvent.Type.Shortcut,
}


class DocumentChangeTracker(QObject):
    """Coalesce user input into one per-document change notification.

    Krita's public Python Notifier has no image-content-changed signal. This
    tracker therefore observes input centrally and lets consumers compare
    their own stable state or pixel digest before doing expensive work.
    """

    def __init__(self) -> None:
        super().__init__()
        self._callbacks: dict[int, dict[int, tuple[Window, Callable[[], None]]]] = {}
        self._documents: dict[int, Document] = {}
        self._timers: dict[int, QTimer] = {}
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def watch(
        self,
        document: Document,
        window: Window,
        owner: object,
        callback: Callable[[], None],
    ) -> None:
        key = id(document)
        self._documents[key] = document
        self._callbacks.setdefault(key, {})[id(owner)] = (window, callback)
        if key not in self._timers:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(CHANGE_DEBOUNCE_MS)
            timer.timeout.connect(lambda document_key=key: self._notify(document_key))
            self._timers[key] = timer

    def unwatch(self, document: Document, owner: object) -> None:
        key = id(document)
        callbacks = self._callbacks.get(key)
        if callbacks is None:
            return
        callbacks.pop(id(owner), None)
        if callbacks:
            return

        self._callbacks.pop(key, None)
        self._documents.pop(key, None)
        timer = self._timers.pop(key, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() not in _INPUT_EVENTS:
            return super().eventFilter(watched, event)
        if self._is_integration_dialog(watched):
            return super().eventFilter(watched, event)

        for document_key, callbacks in self._callbacks.items():
            document = self._documents.get(document_key)
            if document is None:
                continue
            for window, _callback in tuple(callbacks.values()):
                try:
                    view = window.activeView()
                    if view is not None and view.document() == document:
                        self._timers[document_key].start()
                        break
                except RuntimeError:
                    continue
        return super().eventFilter(watched, event)

    @staticmethod
    def _is_integration_dialog(watched: QObject) -> bool:
        current = watched
        while current is not None:
            if isinstance(current, QWidget):
                if current.objectName() in {"LayerSelectionDialog", "comfyui_docker"}:
                    return True
                current = current.parentWidget()
            else:
                current = current.parent()
        return False

    def _notify(self, document_key: int) -> None:
        for window, callback in tuple(self._callbacks.get(document_key, {}).values()):
            document = self._documents.get(document_key)
            try:
                view = window.activeView()
                if document is not None and view is not None and view.document() == document:
                    callback()
            except RuntimeError:
                continue


_TRACKER: DocumentChangeTracker | None = None


def document_change_tracker() -> DocumentChangeTracker:
    global _TRACKER
    if _TRACKER is None:
        _TRACKER = DocumentChangeTracker()
    return _TRACKER
