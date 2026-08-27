from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)


class AudioDenseResult:
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
            f"AudioDenseResult("
            f"point_id={self.point_id!r}, "
            f"score={self.score:.4f}, "
            f"rank={self.rank})"
        )


class AudioQdrantStore:

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "video_audio_windows",
        vector_size: int = 512,
    ):
        self.client = QdrantClient(url=url)
        self.collection_name = collection_name
        self.vector_size = vector_size

    def create_collection(self) -> None:

        collections = (
            self.client
            .get_collections()
            .collections
        )

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
        start_ms: int,
        end_ms: int,
    ) -> str:

        key = (
            f"video={video_id}:"
            f"start={start_ms}:"
            f"end={end_ms}"
        )

        return str(
            uuid5(
                NAMESPACE_URL,
                key,
            )
        )

    def upsert_windows(
        self,
        windows: list,
        embeddings: list,
        video_id: int,
        embedding_version: str = "clap-htsat-unfused",
        quality_scores: list[float] | None = None,
        quality_metadata: list[dict[str, float]] | None = None,
    ) -> None:

        # --------------------------------------------------
        # VALIDATION
        # --------------------------------------------------

        if len(windows) != len(embeddings):
            raise ValueError(
                "windows and embeddings must have "
                "the same length"
            )

        if (
            quality_scores is not None
            and len(windows) != len(quality_scores)
        ):
            raise ValueError(
                "windows and quality_scores must have "
                "the same length"
            )

        if (
            quality_metadata is not None
            and len(windows) != len(quality_metadata)
        ):
            raise ValueError(
                "windows and quality_metadata must have "
                "the same length"
            )

        # --------------------------------------------------
        # BUILD QDRANT POINTS
        # --------------------------------------------------

        points = []

        for index, (window, embedding) in enumerate(
            zip(windows, embeddings)
        ):

            point_id = self.make_point_id(
                video_id=video_id,
                start_ms=window.start_ms,
                end_ms=window.end_ms,
            )

            quality_score = (
                quality_scores[index]
                if quality_scores is not None
                else None
            )

            metadata = (
                quality_metadata[index]
                if quality_metadata is not None
                else {}
            )

            payload = {
                # ------------------------------------------
                # TIMELINE
                # ------------------------------------------

                "video_id": video_id,
                "start_ms": window.start_ms,
                "end_ms": window.end_ms,

                # ------------------------------------------
                # EMBEDDING
                # ------------------------------------------

                "embedding_model": "CLAP",
                "embedding_provider": "laion",
                "embedding_version": embedding_version,
                "modality": "audio",

                # ------------------------------------------
                # AUDIO QUALITY
                # ------------------------------------------

                "speech_ratio": metadata.get(
                    "speech_ratio"
                ),

                "clipping_ratio": metadata.get(
                    "clipping_ratio"
                ),

                "loudness": metadata.get(
                    "loudness"
                ),

                "snr_proxy": metadata.get(
                    "snr_proxy"
                ),

                "snr_norm": metadata.get(
                    "snr_norm"
                ),

                "asr_confidence": metadata.get(
                    "asr_confidence"
                ),

                "quality_score": quality_score,
            }

            vector = (
                embedding.tolist()
                if hasattr(
                    embedding,
                    "tolist",
                )
                else embedding
            )

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        if not points:
            return

        # --------------------------------------------------
        # UPSERT
        # --------------------------------------------------

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def search(
        self,
        vector,
        limit: int = 5,
    ) -> list[AudioDenseResult]:

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
                AudioDenseResult(
                    point_id=str(point.id),
                    score=float(point.score),
                    rank=rank,
                    payload=point.payload or {},
                )
            )

        return results