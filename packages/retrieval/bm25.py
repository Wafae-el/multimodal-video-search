from dataclasses import dataclass
import re
import unicodedata

from rank_bm25 import BM25Okapi


@dataclass(frozen=True)
class BM25Result:
    chunk_id: str
    score: float
    rank: int


class BM25Index:
    """
    Lexical retrieval using BM25.

    Keeps the original text untouched while indexing a normalized
    token representation.
    """

    def __init__(self):
        self.chunk_ids: list[str] = []
        self.texts: list[str] = []
        self.bm25: BM25Okapi | None = None

    @staticmethod
    def normalize(text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        return text.casefold().strip()

    @classmethod
    def tokenize(cls, text: str) -> list[str]:
        text = cls.normalize(text)

        # Supports Latin, Arabic and numeric tokens.
        return re.findall(r"\w+", text, flags=re.UNICODE)

    def build(
        self,
        chunks: list,
    ) -> None:
        self.chunk_ids = [
            chunk.chunk_id
            for chunk in chunks
        ]

        self.texts = [
            chunk.normalized_text
            for chunk in chunks
        ]

        tokenized = [
            self.tokenize(text)
            for text in self.texts
        ]

        self.bm25 = BM25Okapi(tokenized)

    def build_from_payloads(
        self,
        payloads: list[dict],
    ) -> None:
        """
        Build BM25 directly from Qdrant payloads.
        """

        self.chunk_ids = []
        self.texts = []

        for payload in payloads:
            chunk_id = payload.get("chunk_id")
            normalized_text = payload.get(
                "normalized_text"
            )

            if not chunk_id or not normalized_text:
                continue

            self.chunk_ids.append(
                str(chunk_id)
            )

            self.texts.append(
                str(normalized_text)
            )

        tokenized = [
            self.tokenize(text)
            for text in self.texts
        ]

        if not tokenized:
            self.bm25 = None
            return

        self.bm25 = BM25Okapi(tokenized)

    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[BM25Result]:

        if self.bm25 is None:
            raise RuntimeError(
                "BM25 index has not been built."
            )

        query_tokens = self.tokenize(query)

        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        ranked = sorted(
            enumerate(scores),
            key=lambda item: item[1],
            reverse=True,
        )

        results = []

        for rank, (index, score) in enumerate(
            ranked[:limit],
            start=1,
        ):
            results.append(
                BM25Result(
                    chunk_id=self.chunk_ids[index],
                    score=float(score),
                    rank=rank,
                )
            )

        return results