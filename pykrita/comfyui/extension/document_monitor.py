from typing import Any, cast

from krita import Document, Krita
from PyQt5.QtCore import QObject, QTimer, pyqtBoundSignal, pyqtSignal


class DocumentMonitor(QObject):
    on_documents_changed = cast("pyqtBoundSignal", pyqtSignal())
    on_active_document_changed = cast("pyqtBoundSignal", pyqtSignal())

    def __init__(self, interval_ms: int = 300) -> None:
        super().__init__()
        self._krita = Krita.instance()
        self._last_documents = tuple()
        self._last_active_document = None
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_for_changes)
        self._timer.start(interval_ms)
        self._notifier = self._krita.notifier()
        self._notifier.setActive(True)
        self._notifier.viewCreated.connect(self._view_event)  # type: ignore
        self._notifier.viewClosed.connect(self._view_event)  # type: ignore
        self._notifier.imageCreated.connect(self._view_event)  # type: ignore
        self._notifier.imageClosed.connect(self._view_event)  # type: ignore
        self.mapping: dict[str, Document] = {}
        self.document_id_mapping: dict[str, str] = {}

    def test_mappings(self, mappings: dict[str, str]) -> bool:
        return self._resolve_mapping(mappings) is not None

    def assign_name_mappings(self, mappings: dict[str, str]) -> None:
        resolved = self._resolve_mapping(mappings)

        if resolved is None:
            message = "Unable to retrieve valid unique document id mappings"
            raise ValueError(message)

        self.document_id_mapping = dict(mappings)
        self.mapping.clear()
        self.mapping.update(resolved)

    def get_opened_documents(self) -> list[Document]:
        return list(self._last_documents)

    def get_active_document(self) -> Document | None:
        return next((document for document in self._last_documents if self._last_active_document == document), None)

    def document_to_id(self, document: Document) -> str | None:
        for document_id, mapped_document in self.mapping.items():
            if mapped_document == document:
                return document_id

        return None

    def _resolve_mapping(self, mappings: dict[str, str]) -> dict[str, Document] | None:
        if len(mappings) != len(self._last_documents):
            return None

        remaining = dict(mappings)
        resolved: dict[str, Document] = {}

        for doc in self._last_documents:
            document_name = doc.name()
            match = next(
                (mapping_id for mapping_id, mapping_name in remaining.items() if mapping_name == document_name),
                None,
            )

            if match is None:
                return None

            resolved[match] = doc
            remaining.pop(match, None)

        return resolved

    def _current_doc_names(self) -> tuple[str, ...]:
        return tuple(doc.name() for doc in self._krita.documents())

    def _view_event(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401, ARG002
        self._check_for_changes()

    def _check_for_changes(self) -> None:
        current_documents = tuple(self._krita.documents())
        current_active_document = self._krita.activeDocument()

        have_documents_changed = False
        has_active_document_changed = False

        if current_documents != self._last_documents:
            self._last_documents = current_documents
            have_documents_changed = True

        if current_active_document != self._last_active_document:
            self._last_active_document = current_active_document
            has_active_document_changed = True

        if have_documents_changed:
            self.on_documents_changed.emit()

        if has_active_document_changed:
            self.on_active_document_changed.emit()
