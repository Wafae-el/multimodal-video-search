from pathlib import Path

import numpy as np
import open_clip
import torch
from PIL import Image

from packages.visual.encoder import VisualEncoder


class OpenCLIPVisualEncoder(VisualEncoder):

    def __init__(
        self,
        model_name: str = "ViT-B-32",
        pretrained: str = "openai",
        device: str = "cpu",
    ):
        self.device = torch.device(device)

        self.model, _, self.preprocess = (
            open_clip.create_model_and_transforms(
                model_name,
                pretrained=pretrained,
                device=self.device,
            )
        )

        self.tokenizer = open_clip.get_tokenizer(
            model_name
        )

        self.model.eval()

        self.dimension = self.model.visual.output_dim

    @staticmethod
    def _normalize(
        vector: torch.Tensor,
    ) -> torch.Tensor:
        return vector / vector.norm(
            dim=-1,
            keepdim=True,
        ).clamp_min(1e-12)

    def encode_image(
        self,
        image_path: Path,
    ) -> np.ndarray:

        if not image_path.exists():
            raise FileNotFoundError(image_path)

        image = Image.open(image_path).convert("RGB")

        tensor = self.preprocess(image).unsqueeze(0)
        tensor = tensor.to(self.device)

        with torch.inference_mode():
            embedding = self.model.encode_image(tensor)
            embedding = self._normalize(embedding)

        return embedding[0].cpu().numpy()

    def encode_images(
        self,
        image_paths: list[Path],
    ) -> np.ndarray:

        if not image_paths:
            return np.empty(
                (0, self.dimension),
                dtype=np.float32,
            )

        images = []

        for image_path in image_paths:

            if not image_path.exists():
                raise FileNotFoundError(image_path)

            image = Image.open(image_path).convert("RGB")

            images.append(
                self.preprocess(image)
            )

        tensor = torch.stack(images).to(
            self.device
        )

        with torch.inference_mode():
            embeddings = self.model.encode_image(
                tensor
            )

            embeddings = self._normalize(
                embeddings
            )

        return embeddings.cpu().numpy()

    def encode_text(
        self,
        text: str,
    ) -> np.ndarray:

        if not text.strip():
            raise ValueError(
                "Text query cannot be empty"
            )

        tokens = self.tokenizer([text])
        tokens = tokens.to(self.device)

        with torch.inference_mode():
            embedding = self.model.encode_text(
                tokens
            )

            embedding = self._normalize(
                embedding
            )

        return embedding[0].cpu().numpy()