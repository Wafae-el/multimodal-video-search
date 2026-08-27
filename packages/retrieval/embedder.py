from typing import Sequence

from sentence_transformers import SentenceTransformer


class TextEmbedder:
    """
    Generate dense multilingual embeddings for text chunks.
    """

    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    ):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        return self.model.get_embedding_dimension()

    def embed(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self.model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return embeddings.tolist()

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]