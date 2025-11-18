import os

import debugpy
from krita import Krita

from comfyui.extension import ComfyUIExtension
from comfyui.extension.exception_hook import setup_exception_hook

from . import vendors  # noqa: F401


def main() -> None:
    debugpy.listen(5678, in_process_debug_adapter=True)

    if os.environ.get("KRITA_DEBUG", None):
        debugpy.wait_for_client()

        setup_exception_hook()

    krita = Krita.instance()
    krita.addExtension(ComfyUIExtension(krita))


main()
