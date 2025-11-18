import json
from pathlib import Path

CONFIG_PATH = "krita.json"


try:
    with Path(CONFIG_PATH).open() as json_file:
        config = json.load(json_file)
except Exception:  # noqa: BLE001
    config = None
