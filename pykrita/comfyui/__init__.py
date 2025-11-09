from . import vendors # noqa: F401

import os
from krita import Krita
import debugpy

from comfyui.extension import ComfyUIExtension



def main():
    debugpy.listen(5678, in_process_debug_adapter=True)

    if os.environ.get("KRITA_DEBUG", None):
        debugpy.wait_for_client()

    krita = Krita.instance()
    krita.addExtension(ComfyUIExtension(krita))


main()
