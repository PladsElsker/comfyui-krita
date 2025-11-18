import os
import zipfile
from pathlib import Path


def zip_directory(folder_path: str | Path, zip_path: str | Path, ignored: list[str] | None = None) -> None:
    folder_path = Path(os.path.normpath(folder_path)).resolve()
    zip_path = Path(zip_path).resolve()

    if zip_path.exists() and zip_path.is_file():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):  # noqa: B007
            if ignored and root in ignored:
                continue

            for file in files:
                file_path = Path(root) / file
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)
