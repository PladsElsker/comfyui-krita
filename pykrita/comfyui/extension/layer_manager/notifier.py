from typing import cast

from PyQt5.QtCore import QObject, pyqtBoundSignal, pyqtSignal


class PersistentLayerNotifier(QObject):
    on_layer_moved = cast("pyqtBoundSignal", pyqtSignal())
    on_layer_deleted = cast("pyqtBoundSignal", pyqtSignal())
    on_layer_created = cast("pyqtBoundSignal", pyqtSignal())
