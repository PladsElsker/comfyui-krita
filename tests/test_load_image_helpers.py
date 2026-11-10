# ruff: noqa: S101
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import load_image_helpers  # noqa: E402
from load_image_helpers import decode_composited_png  # noqa: E402


def _png_from_rgba_pixels(pixels: list[tuple[int, int, int, int]], width: int, height: int) -> bytes:
    image = Image.new("RGBA", (width, height))
    image.putdata(pixels)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test__given_composite_with_transparency__when_decoding__then_returns_rgb_image_and_inverse_alpha_mask() -> None:
    png = _png_from_rgba_pixels(
        [
            (240, 20, 10, 0),
            (20, 100, 30, 128),
            (10, 20, 30, 255),
        ],
        width=3,
        height=1,
    )

    image, mask = decode_composited_png(
        png,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )

    expected_image = torch.tensor(
        [[[[240, 20, 10], [20, 100, 30], [10, 20, 30]]]],
        dtype=torch.float32,
    ) / 255.0
    expected_mask = torch.tensor([[[1.0, 1.0 - 128.0 / 255.0, 0.0]]], dtype=torch.float32)

    assert image.shape == (1, 1, 3, 3)
    assert mask.shape == (1, 1, 3)
    assert torch.allclose(image, expected_image)
    assert torch.allclose(mask, expected_mask)


def test__given_invalid_png__when_decoding__then_raises_value_error() -> None:
    with pytest.raises(ValueError, match="not a valid image"):
        decode_composited_png(
            b"not a png",
            device=torch.device("cpu"),
            dtype=torch.float32,
        )


def test__given_composite_exceeding_pixel_limit__when_decoding__then_rejects_before_tensor_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(load_image_helpers, "MAX_LOAD_IMAGE_PIXELS", 0)
    png = _png_from_rgba_pixels([(0, 0, 0, 0)], width=1, height=1)

    with pytest.raises(ValueError, match="unsupported dimensions"):
        decode_composited_png(
            png,
            device=torch.device("cpu"),
            dtype=torch.float32,
        )
