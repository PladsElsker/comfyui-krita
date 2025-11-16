from typing import Dict, cast

from krita import Krita, Document
from PyQt5.QtCore import QObject, pyqtBoundSignal, pyqtSignal, QTimer


class DocumentMonitor(QObject):
    on_documents_changed = cast(pyqtBoundSignal, pyqtSignal())
    on_active_document_changed = cast(pyqtBoundSignal, pyqtSignal(str))

    def __init__(self, interval_ms=300):
        super().__init__()
        self._krita = Krita.instance()
        self._last_docs = tuple()
        self._last_active_doc = None
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_for_changes)
        self._timer.start(interval_ms)
        self.mapping: dict[str, Document] = {}
    
    def test_mappings(self, mappings: Dict[str, str]) -> bool:
        return self._resolve_mapping(mappings) is not None

    def assign_name_mappings(self, mappings: Dict[str, str]):
        resolved = self._resolve_mapping(mappings)

        if resolved is None:
            raise ValueError("Unable to retrieve valid unique document id mappings")
        
        self.mapping.clear()
        self.mapping.update(resolved)

    def get_last_docs(self):
        return list(self._last_docs)

    def _resolve_mapping(self, mappings: Dict[str, str]) -> Dict[str, Document] | None:
        if len(mappings) != len(self._last_docs):
            return None

        remaining = dict(mappings)
        resolved: Dict[str, Document] = {}

        for doc in self._last_docs:
            document_name = doc.name()
            match = next(
                (mapping_id for mapping_id, mapping_name in remaining.items() if mapping_name == document_name),
                None
            )

            if match is None:
                return None

            resolved[match] = doc
            remaining.pop(match, None)

        return resolved

    def _current_doc_names(self) -> tuple[str, ...]:
        return tuple(doc.name() for doc in self._krita.documents())

    def _check_for_changes(self):
        current_docs = tuple(self._krita.documents())
        if current_docs != self._last_docs:
            self._last_docs = current_docs
            self.on_documents_changed.emit()
