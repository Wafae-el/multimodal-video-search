from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)


class VisualDenseResult:
    def __init__(
        self,
        point_id: str,
        score: float,
        rank: int,
        payload: dict[str, Any],
    ):
        self.point_id = point_id
        self.score = score
        self.rank = rank
        self.payload = payload

    def __repr__(self):
        return (
            f"VisualDenseResult("
            f"point_id={self.point_id!r}, "
            f"score={self.score:.4f}, "
            f"rank={self.rank})"
        )


class VisualQdrantStore:

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "video_visual_frames",
        vector_size: int = 512,
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

    @staticmethod
    def make_point_id(
        video_id: int,
        scene_id: int,
        timestamp_ms: int,
    ) -> str:
        key = (
            f"video={video_id}:"
            f"scene={scene_id}:"
            f"time={timestamp_ms}"
        )

        return str(uuid5(NAMESPACE_URL, key))

    def upsert_frames(
        self,
        frames: list,
        embeddings: list,
        video_id: int,
        embedding_version: str = "openclip-vit-b32-v1",
    ) -> None:

        if len(frames) != len(embeddings):
            raise ValueError(
                "frames and embeddings must have the same length"
            )

        points = []

        for frame, embedding in zip(frames, embeddings):

            point_id = self.make_point_id(
                video_id=video_id,
                scene_id=frame.scene_id,
                timestamp_ms=frame.timestamp_ms,
            )

            payload = {
                "video_id": video_id,
                "scene_id": frame.scene_id,
                "timestamp_ms": frame.timestamp_ms,
                "object_key": getattr(
                    frame,
                    "object_key",
                    None,
                ),
                "embedding_model": "ViT-B-32",
                "embedding_provider": "openai",
                "embedding_version": embedding_version,
                "modality": "image",
            }

            vector = (
                embedding.tolist()
                if hasattr(embedding, "tolist")
                else embedding
            )

            points.append(
                PointStruct(
                    id=point_id,
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
        vector,
        limit: int = 5,
    ) -> list[VisualDenseResult]:

        query_vector = (
            vector.tolist()
            if hasattr(vector, "tolist")
            else vector
        )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )

        results = []

        for rank, point in enumerate(
            response.points,
            start=1,
        ):
            results.append(
                VisualDenseResult(
                    point_id=str(point.id),
                    score=float(point.score),
                    rank=rank,
                    payload=point.payload or {},
                )
            )

        return results