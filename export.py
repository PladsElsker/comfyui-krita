import logging

from krita_hook.config import config
from krita_hook.zip import zip_directory
from update_vendors import update_vendors

logging.info("Updating vendors...")
update_vendors()

logging.info("Zip...")
zip_directory(config["ZipFrom"], f'{config["ExtensionName"]}.zip', ignored=["__pycache__"])
