import logging
from threading import Thread

from krita_hook.config import config
from krita_hook.export import export_directory
from krita_hook.watcher import ChangeEvent, Watcher
from krita_hook.zip import zip_directory


def start_hook() -> None:
    if not config:
        logging.info("No krita config file found")
        return

    watcher_thread = Thread(
        target=Watcher(
            config["Watch"],
            [
                LogChanges(),
                # ZipProject(),  # noqa: ERA001
                # ExportDirectory(),  # noqa: ERA001
            ],
        ).run,
    )
    watcher_thread.start()
    logging.info("Started krita hook")
    watcher_thread.join()


class ZipProject(ChangeEvent):
    def handle(self, root: str) -> None:  # noqa: ARG002
        zip_directory(config["ZipFrom"], f'{config["ExtensionName"]}.zip', ignored=["__pycache__"])


class ExportDirectory(ChangeEvent):
    def handle(self, root: str) -> None:  # noqa: ARG002
        export_directory(config["ExportFrom"], config["ExportTo"])


class LogChanges(ChangeEvent):
    def handle(self, root: str) -> None:  # noqa: ARG002
        logging.info("Changes detected")
