from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QWidget


class WorkflowHeader(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(4, 12, 4, 4)

        self.workflow_label = QLabel("Workflow: —")
        self.workflow_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_layout.addWidget(self.workflow_label)

        self.document_label = QLabel("Document: —")
        self.document_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_layout.addWidget(self.document_label)

    def set_workflow_name(self, name: str) -> None:
        display = name if name else "—"
        self.workflow_label.setText(f"Workflow: {display}")

    def set_document_name(self, name: str) -> None:
        display = name if name else "—"
        self.document_label.setText(f"Document: {display}")
