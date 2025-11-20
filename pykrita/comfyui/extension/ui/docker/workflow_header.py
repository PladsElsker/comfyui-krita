from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class WorkflowHeader(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(4, 12, 4, 4)

        self.container = QHBoxLayout()
        self.row1 = QVBoxLayout()
        self.row2 = QVBoxLayout()

        self.row1.addWidget(QLabel("Workflow: "))
        self.row1.addWidget(QLabel("Document: "))

        self.workflow_label = QLabel("—")
        self.document_label = QLabel("—")

        self.row2.addWidget(self.workflow_label)
        self.row2.addWidget(self.document_label)

        self.container.addLayout(self.row1)
        self.container.addLayout(self.row2)
        self.container.addStretch(1)

        self.main_layout.addLayout(self.container)

    def set_workflow_name(self, name: str) -> None:
        display = name if name else "—"
        self.workflow_label.setText(display)

    def set_document_name(self, name: str) -> None:
        display = name if name else "—"
        self.document_label.setText(display)
