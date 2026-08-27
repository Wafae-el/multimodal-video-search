from pathlib import Path

import cv2
from PIL import Image


class FrameQuality:

    def is_black(
        self,
        image_path: Path,
        threshold: int = 10,
    ) -> bool:
        """
        Detect frames that are almost completely black.
        """

        image = Image.open(image_path).convert("L")

        pixels = list(image.getdata())

        if not pixels:
            return True

        mean = sum(pixels) / len(pixels)

        return mean < threshold

    def is_blurry(
        self,
        image_path: Path,
        threshold: float = 100.0,
    ) -> bool:
        """
        Detect blurry frames using Laplacian variance.
        """

        image = cv2.imread(str(image_path))

        if image is None:
            raise FileNotFoundError(image_path)

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

        variance = cv2.Laplacian(
            gray,
            cv2.CV_64F,
        ).var()

        return variance < threshold

    def is_bright(
    self,
    image_path: Path,
    threshold: int = 252,
    ratio: float = 0.98,
    ) -> bool:
        """
        Detect frames that are almost completely white.

        Bright presentation/screen-capture frames are allowed.
        A frame is rejected only when an extreme majority
        of its pixels are near-white.
        """

        image = Image.open(image_path).convert("L")
        pixels = list(image.getdata())
        if not pixels:
            return False

        bright_pixels = sum(
            pixel >= threshold
            for pixel in pixels
        )

        bright_ratio = bright_pixels / len(pixels)
        return bright_ratio >= ratio

    def resolution(
        self,
        image_path: Path,
    ) -> tuple[int, int]:
        """
        Return frame resolution as (width, height).
        """

        image = Image.open(image_path)

        return image.width, image.height

    def has_sufficient_resolution(
        self,
        image_path: Path,
        min_width: int = 320,
        min_height: int = 180,
    ) -> bool:
        """
        Check that the frame resolution is sufficient
        for visual embedding.
        """

        width, height = self.resolution(
            image_path
        )

        return (
            width >= min_width
            and height >= min_height
        )

    def is_usable(
        self,
        image_path: Path,
        blur_threshold: float = 100.0,
        black_threshold: int = 10,
        bright_threshold: int = 252,
        bright_ratio: float = 0.98,
        min_width: int = 320,
        min_height: int = 180,
    ) -> bool:
        """
        Return True only when the frame passes all
        visual quality checks.
        """

        if self.is_black(
            image_path,
            threshold=black_threshold,
        ):
            return False

        if self.is_blurry(
            image_path,
            threshold=blur_threshold,
        ):
            return False

        if self.is_bright(
            image_path,
            threshold=bright_threshold,
            ratio=bright_ratio,
        ):
            return False

        if not self.has_sufficient_resolution(
            image_path,
            min_width=min_width,
            min_height=min_height,
        ):
            return False

        return True