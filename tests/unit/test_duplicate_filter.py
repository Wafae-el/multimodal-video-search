from pathlib import Path

import cv2
import numpy as np

from packages.media.duplicate_filter import DuplicateFilter


def test_identical_images(tmp_path):

    image = np.full(
        (100, 100, 3),
        120,
        dtype=np.uint8,
    )

    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b.jpg"

    cv2.imwrite(str(p1), image)
    cv2.imwrite(str(p2), image)

    filt = DuplicateFilter()

    assert filt.are_similar(p1, p2)


def test_different_images(tmp_path):

    img1 = np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )

    img2 = np.full(
        (100, 100, 3),
        255,
        dtype=np.uint8,
    )

    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b.jpg"

    cv2.imwrite(str(p1), img1)
    cv2.imwrite(str(p2), img2)

    filt = DuplicateFilter()

    assert not filt.are_similar(p1, p2)