from pathlib import Path

from PIL import Image

from packages.media.frame_quality import FrameQuality

import cv2
import numpy as np


def test_black_image(tmp_path):
    image = Image.new("RGB", (100, 100), (0, 0, 0))

    path = tmp_path / "black.jpg"

    image.save(path)

    quality = FrameQuality()

    assert quality.is_black(path)


def test_white_image(tmp_path):
    image = Image.new("RGB", (100, 100), (255, 255, 255))

    path = tmp_path / "white.jpg"

    image.save(path)

    quality = FrameQuality()

    assert not quality.is_black(path)

def test_blurry_image(tmp_path):
    image = np.full(
        (200, 200, 3),
        150,
        dtype=np.uint8,
    )

    path = tmp_path / "blur.jpg"

    cv2.imwrite(str(path), image)

    quality = FrameQuality()

    assert quality.is_blurry(path)

def test_sharp_image(tmp_path):
    image = np.zeros(
        (300, 300),
        dtype=np.uint8,
    )

    cv2.line(
        image,
        (0, 0),
        (299, 299),
        255,
        4,
    )

    path = tmp_path / "sharp.jpg"

    cv2.imwrite(str(path), image)

    quality = FrameQuality()

    assert not quality.is_blurry(path)