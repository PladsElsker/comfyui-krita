from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class WorkflowHeader(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.workflow_title = QLabel("Workflow: ")

        self.document_title = QLabel("Document: ")

        self.workflow_label = QLabel("—")
        document_label_accent = self.document_label.palette().color(QPalette.ColorRole.HighlightedText)
        self.document_label.setStyleSheet(f"color: {document_label_accent.name()};")

        self.document_label = QLabel("—")
        workflow_label_accent = self.workflow_label.palette().color(QPalette.ColorRole.HighlightedText)
        self.workflow_label.setStyleSheet(f"color: {workflow_label_accent.name()};")

        self.row1 = QVBoxLayout()
        self.row1.addWidget(self.workflow_title)
        self.row1.addWidget(self.document_title)

        self.row2 = QVBoxLayout()
        self.row2.addWidget(self.workflow_label)
        self.row2.addWidget(self.document_label)

        self.container = QHBoxLayout()
        self.container.addLayout(self.row1)
        self.container.addLayout(self.row2)
        self.container.addStretch(1)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.addLayout(self.container)

    def set_workflow_name(self, name: str) -> None:
        display = name if name else "—"
        self.workflow_label.setText(display)

    def set_document_name(self, name: str) -> None:
        display = name if name else "—"
        self.document_label.setText(display)
