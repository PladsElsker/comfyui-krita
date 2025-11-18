import logging

from krita_hook.config import config
from krita_hook.export import export_directory
from update_vendors import update_vendors

logging.info("Updating vendors...")
update_vendors()

logging.info("Export...")
export_directory(config["ExportFrom"], config["ExportTo"])
