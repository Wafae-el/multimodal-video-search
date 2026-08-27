from pathlib import Path

import cv2
import numpy as np


class DuplicateFilter:

    def are_similar(
        self,
        image1: Path,
        image2: Path,
        threshold: float = 5.0,
    ) -> bool:

        img1 = cv2.imread(str(image1))

        img2 = cv2.imread(str(image2))

        if img1 is None or img2 is None:
            raise FileNotFoundError()

        if img1.shape != img2.shape:
            return False

        diff = np.mean(
            np.abs(
                img1.astype(np.float32)
                - img2.astype(np.float32)
            )
        )

        return diff < threshold