from krita import DockWidget
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from comfyui.extension.ui.micro.labels import ElidedLabel


class WorkflowHeader(QFrame):
    def __init__(self, docker: DockWidget) -> None:
        super().__init__()

        self.workflow_title = QLabel("Workflow: ")

        self.document_title = QLabel("Document: ")

        self.document_label = ElidedLabel("—")
        document_label_accent = self.document_label.palette().color(QPalette.ColorRole.HighlightedText)
        self.document_label.setStyleSheet(f"color: {document_label_accent.name()};")

        self.workflow_label = ElidedLabel("—")
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

        def get_width_fun() -> int:
            self.main_layout.activate()

            w0 = self.row1.geometry().width()
            w1 = self.row2.geometry().width()
            wt = docker.width()
            w2 = wt - (w0 + w1)
            return w1 + w2 - 24

        self.document_label.set_elided_width_producer(get_width_fun)
        self.workflow_label.set_elided_width_producer(get_width_fun)

    def set_workflow_name(self, name: str) -> None:
        display = name if name else "—"
        self.workflow_label.setText(display)

    def set_document_name(self, name: str) -> None:
        display = name if name else "—"
        self.document_label.setText(display)
