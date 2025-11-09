from krita_hook.zip import zip_directory
from krita_hook.config import config
from update_vendors import update_vendors


print('Updating vendors...')
update_vendors()

print('Zip...')
zip_directory(config['ZipFrom'], f'{config["ExtensionName"]}.zip', ignored=['__pycache__'])
