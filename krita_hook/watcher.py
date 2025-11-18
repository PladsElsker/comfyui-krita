import logging
import time
from pathlib import Path
from typing import Any

from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from krita_hook.debounce import Debouncer


class Watcher:
    def __init__(self, directory: str | Path, events: list["ChangeEvent"]) -> None:
        self.observer = Observer()
        self.directory = directory
        self.events = events

    def run(self) -> None:
        event_handler = Handler(self)
        self.observer.schedule(event_handler, str(self.directory), recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except:  # noqa: E722
            self.observer.stop()
            logging.info("Observer Stopped")

        self.observer.join()


class Handler(FileSystemEventHandler):
    def __init__(self, watcher: Watcher) -> None:
        self.watcher = watcher
        self.handle = Debouncer(10, self._handle)

    def _handle(self, event: Any) -> None:  # noqa: ANN401, ARG002
        [e.handle(str(self.watcher.directory)) for e in self.watcher.events if isinstance(e, ChangeEvent)]

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        self.handle.call(event)

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        self.handle.call(event)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        self.handle.call(event)


class ChangeEvent:
    def handle(self, root: str) -> None:
        raise NotImplementedError
