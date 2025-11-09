from krita_hook.export import export_directory
from krita_hook.config import config
from update_vendors import update_vendors


print('Updating vendors...')
update_vendors()

print('Export...')
export_directory(config['ExportFrom'], config['ExportTo'])
