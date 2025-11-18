from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QWidget


class WorkflowHeader(QWidget):
    workflow_changed = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workflow_name = None

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(4, 12, 4, 4)

        self.label = QLabel("Workflow: —")
        self.label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_layout.addWidget(self.label)

    def set_workflow_name(self, name: str) -> None:
        self._workflow_name = name
        display = name if name else "—"
        self.label.setText(f"Workflow: {display}")
