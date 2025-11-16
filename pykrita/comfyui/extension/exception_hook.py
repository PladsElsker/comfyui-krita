import sys
import traceback
from PyQt5.QtCore import qCritical


_original_excepthook = sys.excepthook


def _exception_hook(exception_type, exception_value, exception_traceback):
    if issubclass(exception_type, KeyboardInterrupt):
        _original_excepthook(exception_type, exception_value, exception_traceback)
        return

    trace = "".join(traceback.format_exception(exception_type, exception_value, exception_traceback))
    qCritical(f"Uncaught exception:\n{trace}")

    _original_excepthook(exception_type, exception_value, exception_traceback)


def setup_exception_hook():
    sys.excepthook = _exception_hook
