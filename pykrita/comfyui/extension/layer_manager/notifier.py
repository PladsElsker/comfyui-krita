from typing import cast

from PyQt5.QtCore import QObject, pyqtBoundSignal, pyqtSignal


class PersistentLayerNotifier(QObject):
    user_unrendered = cast("pyqtBoundSignal", pyqtSignal())
    user_rendered = cast("pyqtBoundSignal", pyqtSignal())
    user_moved = cast("pyqtBoundSignal", pyqtSignal(object))
    user_renamed = cast("pyqtBoundSignal", pyqtSignal(str))
