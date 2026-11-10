from io import BytesIO

import numpy as np
from PIL import Image
from torch import Tensor, from_numpy


MAX_LOAD_IMAGE_PIXELS = 16_000_000


def decode_composited_png(
    image_data: bytes,
    *,
    device: object,
    dtype: object,
) -> tuple[Tensor, Tensor]:
    try:
        with Image.open(BytesIO(image_data)) as image:
            if image.format != "PNG":
                raise ValueError("The Krita layer snapshot must be a PNG")
            rgba_image = image.convert("RGBA")
            width, height = rgba_image.size
            if width < 1 or height < 1 or width * height > MAX_LOAD_IMAGE_PIXELS:
                raise ValueError("The Krita layer snapshot has unsupported dimensions")
            pixel_data = rgba_image.tobytes()
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("The Krita layer snapshot is not a valid image") from error

    rgba = np.frombuffer(pixel_data, dtype=np.uint8).reshape(height, width, 4)
    rgb = rgba[..., :3].astype(np.float32)
    rgb *= 1.0 / 255.0
    alpha = rgba[..., 3].astype(np.float32)
    alpha *= 1.0 / 255.0

    image_tensor = from_numpy(rgb).unsqueeze(0)
    # ComfyUI masks use 1 for fully masked and 0 for fully kept pixels.
    mask_tensor = (1.0 - from_numpy(alpha)).unsqueeze(0)
    return image_tensor.to(device=device, dtype=dtype), mask_tensor.to(device=device, dtype=dtype)
