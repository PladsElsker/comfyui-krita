import threading
from collections.abc import Callable


class Debouncer:
    def __init__(self, wait_time: float, func: Callable) -> None:
        self.wait_time = wait_time
        self.func = func
        self.timer = None

    def call(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(self.wait_time, self.func, args=args, kwargs=kwargs)
        self.timer.start()

    def cancel(self) -> None:
        if self.timer:
            self.timer.cancel()
