# Keep this line at the top.
from . import vendors  # noqa: F401, I001

import os

from krita import Krita

from comfyui.extension.exception_hook import setup_exception_hook


def main() -> None:
    setup_exception_hook()

    if os.environ.get("KRITA_DEBUG", None):
        import debugpy  # noqa: PLC0415

        debugpy.listen(5678, in_process_debug_adapter=True)
        debugpy.wait_for_client()

    from comfyui.extension import ComfyUIExtension  # noqa: PLC0415

    krita = Krita.instance()
    krita.addExtension(ComfyUIExtension(krita))


main()
