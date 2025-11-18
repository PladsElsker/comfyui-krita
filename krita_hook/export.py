import logging
import shutil
from pathlib import Path


def export_directory(source_dir: str | Path, target_dir: str | Path, target_exists: bool = True, same_name: bool = True) -> None:  # noqa: FBT002
    if same_name and Path(source_dir).name != Path(target_dir).name:
        message = "Source and target directory names don't match"
        raise FileNotFoundError(message)

    if not Path(source_dir).exists():
        message = f"Source directory does not exist: {source_dir}"
        raise FileNotFoundError(message)

    if target_exists and not Path(target_dir).exists():
        message = f"Target directory must exist: {source_dir}"
        raise FileNotFoundError(message)

    if Path(target_dir).exists():
        try:
            shutil.rmtree(target_dir)
        except Exception as e:  # noqa: BLE001
            logging.critical(e)

    shutil.copytree(source_dir, target_dir)
