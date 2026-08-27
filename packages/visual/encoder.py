from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


class VisualEncoder(ABC):

    @abstractmethod
    def encode_image(
        self,
        image_path: Path,
    ) -> np.ndarray:
        pass

    @abstractmethod
    def encode_text(
        self,
        text: str,
    ) -> np.ndarray:
        pass