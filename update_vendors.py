import logging
import shutil
import sys
from pathlib import Path


def _update_vendors_func(
    venv_dir: str = "venv-pkg",
    plugin_dir: str = str(Path("pykrita") / "comfyui"),
    clean: bool = True,  # noqa: FBT002
    ignore_list: list[str] = [],
) -> None:
    base = Path(__file__).resolve().parent
    venv_site = base / venv_dir / "Lib" / "site-packages"

    if not venv_site or not venv_site.exists():
        message = f"[!] Could not locate site-packages inside {venv_dir}"
        logging.info(message)
        sys.exit(1)

    vendor_dir = base / plugin_dir / "vendor"

    if clean and vendor_dir.exists():
        shutil.rmtree(vendor_dir)

    vendor_dir.mkdir(parents=True, exist_ok=True)

    message = f"Copying from {venv_site}"
    logging.info(message)
    for item in venv_site.iterdir():
        name = item.name

        if any(name.startswith(prefix.rstrip("*")) or name.endswith(suffix.lstrip("*")) for prefix in ignore_list for suffix in ignore_list):
            continue

        if name.endswith((".dist-info", ".data", "__pycache__")):
            continue

        dest = vendor_dir / name

        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    message = f"Vendor folder updated: {vendor_dir}"
    logging.info(message)


def update_vendors() -> None:
    _update_vendors_func(ignore_list=["pip", "watchdog", "PyQt5", "setuptools"])


if __name__ == "__main__":
    update_vendors()
