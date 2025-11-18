import json
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QStandardPaths


class Config(dict):
    def __init__(self, app_name: str = "KritaComfyUI-15347", filename: str = "config.json") -> None:
        super().__init__()
        self._app_name = app_name
        self._filename = filename
        self._path = self._resolve_path()
        self._load()

    def save(self) -> None:
        with Path(self._path).open("w", encoding="utf-8") as f:
            json.dump(self, f, indent=2, ensure_ascii=False)

    def _resolve_path(self) -> Path:
        base_dir = QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation)
        app_dir = Path(base_dir) / self._app_name
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / self._filename

    def _load(self) -> None:
        if not self._path.exists():
            return

        with self._path.open(encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                self.update(data)

    def __setitem__(self, key: str, value: Any) -> None:  # noqa: ANN401
        super().__setitem__(key, value)
        self.save()

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        self.save()

    @property
    def path(self) -> Path:
        return self._path
