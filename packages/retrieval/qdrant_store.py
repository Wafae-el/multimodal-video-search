from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)


class DenseResult:
    def __init__(
        self,
        chunk_id: str,
        score: float,
        rank: int,
        payload: dict[str, Any],
    ):
        self.chunk_id = chunk_id
        self.score = score
        self.rank = rank
        self.payload = payload

    def __repr__(self):
        return (
            f"DenseResult("
            f"chunk_id={self.chunk_id!r}, "
            f"score={self.score:.4f}, "
            f"rank={self.rank})"
        )


class QdrantStore:

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "video_transcripts",
        vector_size: int = 384,
    ):
        self.client = QdrantClient(url=url)
        self.collection_name = collection_name
        self.vector_size = vector_size

    def create_collection(self) -> None:
        collections = self.client.get_collections().collections

        if any(
            collection.name == self.collection_name
            for collection in collections
        ):
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE,
            ),
        )

    def upsert_chunks(
        self,
        chunks: list,
        embeddings: list[list[float]],
        video_id: int | None = None,
        language: str | None = None,
    ) -> None:

        if len(chunks) != len(embeddings):
            raise ValueError(
                "chunks and embeddings must have the same length"
            )

        points = []

        for index, (chunk, vector) in enumerate(
            zip(chunks, embeddings)
        ):
            payload = {
                "chunk_id": chunk.chunk_id,
                "video_id": video_id,
                "start_ms": chunk.start_ms,
                "end_ms": chunk.end_ms,
                "text": chunk.text,
                "normalized_text": chunk.normalized_text,
                "source_segment_ids": chunk.source_segment_ids,
                "confidence": chunk.confidence,
                "language": language,
            }

            points.append(
                PointStruct(
                    id=index + 1,
                    vector=vector,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def search(
        self,
        vector: list[float],
        limit: int = 5,
    ) -> list[DenseResult]:

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
            with_payload=True,
        )

        results = []

        for rank, point in enumerate(
            response.points,
            start=1,
        ):
            payload = point.payload or {}

            results.append(
                DenseResult(
                    chunk_id=payload.get(
                        "chunk_id",
                        str(point.id),
                    ),
                    score=float(point.score),
                    rank=rank,
                    payload=payload,
                )
            )

        return results

    def get_all_payloads(self) -> list[dict]:
        """
        Retrieve all transcript payloads from Qdrant.
        """

        payloads = []
        offset = None

        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for point in points:
                payload = point.payload or {}

                if payload:
                    payloads.append(payload)

            if next_offset is None:
                break

            offset = next_offset

        return payloads