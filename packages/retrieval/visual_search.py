from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from packages.visual.openclip_encoder import OpenCLIPVisualEncoder
from packages.visual.similarity import (
    ClipSimilarity,
    VisualSimilarity,
    aggregate_clip_similarity,
    cosine_similarity_matrix,
    l2_normalize,
    suppress_duplicate_frames,
    top_k_similar,
)
from packages.retrieval.visual_qdrant_store import (
    VisualDenseResult,
    VisualQdrantStore,
)


@dataclass
class VisualSearchResult:
    """
    Final visual-search result.

    One result corresponds to one archive frame and contains
    enough metadata to locate the frame and its timestamp.
    """

    video_id: int
    scene_id: int
    timestamp_ms: int
    object_key: str | None
    score: float
    point_id: str
    rank: int
    preview: str | None = None

    def __repr__(self) -> str:
        return (
            "VisualSearchResult("
            f"video_id={self.video_id}, "
            f"scene_id={self.scene_id}, "
            f"timestamp_ms={self.timestamp_ms}, "
            f"score={self.score:.4f}, "
            f"rank={self.rank})"
        )


@dataclass
class VisualClipResult:
    """
    Aggregated result at scene/clip level.
    """

    clip_id: str
    video_id: int
    scene_id: int
    score: float
    max_score: float
    top_r_mean: float
    matched_frames: list[int]
    frames: list[VisualSearchResult]


class VisualSearchService:
    """
    Real visual search service.

    Supported query types:

    - text -> archive frames
    - image -> archive frames
    - multiple image frames -> clip/scene ranking

    Pipeline:

        query
          ↓
        OpenCLIP
          ↓
        normalized embedding
          ↓
        Qdrant
          ↓
        duplicate suppression
          ↓
        Top-K
          ↓
        scene/clip aggregation
    """

    def __init__(
        self,
        *,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = "video_visual_frames",
        model_name: str = "ViT-B-32",
        pretrained: str = "openai",
        device: str = "cpu",
        beta: float = 0.7,
        top_r: int = 3,
        duplicate_threshold: float = 0.98,
    ):
        self.encoder = OpenCLIPVisualEncoder(
            model_name=model_name,
            pretrained=pretrained,
            device=device,
        )

        self.store = VisualQdrantStore(
            url=qdrant_url,
            collection_name=collection_name,
            vector_size=self.encoder.dimension,
        )

        self.store.create_collection()

        self.beta = beta
        self.top_r = top_r
        self.duplicate_threshold = duplicate_threshold

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _result_from_qdrant(
        result: VisualDenseResult,
        rank: int,
    ) -> VisualSearchResult:

        payload = result.payload

        return VisualSearchResult(
            video_id=int(payload["video_id"]),
            scene_id=int(payload["scene_id"]),
            timestamp_ms=int(payload["timestamp_ms"]),
            object_key=payload.get("object_key"),
            score=float(result.score),
            point_id=result.point_id,
            rank=rank,
            preview=payload.get("preview"),
        )

    @staticmethod
    def _deduplicate_results(
        results: list[VisualDenseResult],
        *,
        threshold: float,
    ) -> list[VisualDenseResult]:

        if not results:
            return []

        matches: list[VisualSimilarity] = []
        archive_frame_keys: list[str] = []

        for index, result in enumerate(results):

            payload = result.payload

            key = (
                f"{payload.get('video_id')}:"
                f"{payload.get('scene_id')}:"
                f"{payload.get('timestamp_ms')}:"
                f"{payload.get('object_key')}"
            )

            archive_frame_keys.append(key)

            matches.append(
                VisualSimilarity(
                    query_index=0,
                    archive_index=index,
                    score=float(result.score),
                )
            )

        kept = suppress_duplicate_frames(
            matches,
            archive_frame_keys,
            threshold=threshold,
        )

        deduplicated = [
            results[match.archive_index]
            for match in kept
        ]

        return deduplicated

    # ------------------------------------------------------------------
    # Text -> Frame
    # ------------------------------------------------------------------

    def search_text(
        self,
        text: str,
        *,
        limit: int = 10,
        deduplicate: bool = True,
    ) -> list[VisualSearchResult]:
        """
        Search archive frames using a text query.
        """

        if not text.strip():
            raise ValueError(
                "Text query cannot be empty"
            )

        embedding = self.encoder.encode_text(
            text
        )

        embedding = l2_normalize(
            embedding
        )[0]

        raw_results = self.store.search(
            embedding,
            limit=limit,
        )

        if deduplicate:
            raw_results = self._deduplicate_results(
                raw_results,
                threshold=self.duplicate_threshold,
            )

        results = []

        for rank, result in enumerate(
            raw_results,
            start=1,
        ):
            results.append(
                self._result_from_qdrant(
                    result,
                    rank,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Image -> Frame
    # ------------------------------------------------------------------

    def search_image(
        self,
        image_path: Path,
        *,
        limit: int = 10,
        deduplicate: bool = True,
    ) -> list[VisualSearchResult]:
        """
        Search archive frames using one image.
        """

        image_path = Path(image_path)

        embedding = self.encoder.encode_image(
            image_path
        )

        embedding = l2_normalize(
            embedding
        )[0]

        raw_results = self.store.search(
            embedding,
            limit=limit,
        )

        if deduplicate:
            raw_results = self._deduplicate_results(
                raw_results,
                threshold=self.duplicate_threshold,
            )

        results = []

        for rank, result in enumerate(
            raw_results,
            start=1,
        ):
            results.append(
                self._result_from_qdrant(
                    result,
                    rank,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Multiple query frames -> archive
    # ------------------------------------------------------------------

    def search_frames(
        self,
        image_paths: Iterable[Path],
        *,
        per_query_limit: int = 10,
        final_limit: int = 10,
    ) -> list[VisualSearchResult]:
        """
        Search the archive using multiple query frames.

        Each query frame is encoded independently.
        Results are then combined and ranked.
        """

        paths = [
            Path(path)
            for path in image_paths
        ]

        if not paths:
            raise ValueError(
                "image_paths cannot be empty"
            )

        embeddings = self.encoder.encode_images(
            paths
        )

        embeddings = l2_normalize(
            embeddings
        )

        all_results: list[
            VisualSearchResult
        ] = []

        for query_index, embedding in enumerate(
            embeddings
        ):

            raw_results = self.store.search(
                embedding,
                limit=per_query_limit,
            )

            raw_results = self._deduplicate_results(
                raw_results,
                threshold=self.duplicate_threshold,
            )

            for result in raw_results:

                item = self._result_from_qdrant(
                    result,
                    rank=result.rank,
                )

                all_results.append(item)

        if not all_results:
            return []

        # Same archive frame may be returned by several
        # query frames. Keep the strongest match.
        best_by_frame: dict[
            tuple[int, int, int],
            VisualSearchResult,
        ] = {}

        for result in all_results:

            key = (
                result.video_id,
                result.scene_id,
                result.timestamp_ms,
            )

            previous = best_by_frame.get(key)

            if (
                previous is None
                or result.score > previous.score
            ):
                best_by_frame[key] = result

        results = sorted(
            best_by_frame.values(),
            key=lambda item: item.score,
            reverse=True,
        )

        results = results[
            :final_limit
        ]

        return [
            VisualSearchResult(
                video_id=result.video_id,
                scene_id=result.scene_id,
                timestamp_ms=result.timestamp_ms,
                object_key=result.object_key,
                score=result.score,
                point_id=result.point_id,
                rank=rank,
                preview=result.preview,
            )
            for rank, result in enumerate(
                results,
                start=1,
            )
        ]

    # ------------------------------------------------------------------
    # Scene / Clip aggregation
    # ------------------------------------------------------------------

    def aggregate_results_by_scene(
        self,
        results: Iterable[VisualSearchResult],
    ) -> list[VisualClipResult]:
        """
        Aggregate frame matches by video + scene.

        Formula:

            S_clip =
                beta * max(score)
                +
                (1 - beta) * mean(top-r scores)
        """

        groups: dict[
            tuple[int, int],
            list[VisualSearchResult],
        ] = {}

        for result in results:

            key = (
                result.video_id,
                result.scene_id,
            )

            groups.setdefault(
                key,
                [],
            ).append(result)

        aggregated: list[
            VisualClipResult
        ] = []

        for (
            video_id,
            scene_id,
        ), frames in groups.items():

            frames = sorted(
                frames,
                key=lambda item: item.score,
                reverse=True,
            )

            scores = [
                frame.score
                for frame in frames
            ]

            matched_frames = [
                frame.timestamp_ms
                for frame in frames[
                    :self.top_r
                ]
            ]

            clip_id = (
                f"video={video_id}:"
                f"scene={scene_id}"
            )

            clip = aggregate_clip_similarity(
                clip_id=clip_id,
                frame_scores=scores,
                matched_frames=matched_frames,
                beta=self.beta,
                top_r=self.top_r,
            )

            aggregated.append(
                VisualClipResult(
                    clip_id=clip.clip_id,
                    video_id=video_id,
                    scene_id=scene_id,
                    score=clip.score,
                    max_score=clip.max_score,
                    top_r_mean=clip.top_r_mean,
                    matched_frames=clip.matched_frames,
                    frames=frames,
                )
            )

        aggregated.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        return aggregated

    # ------------------------------------------------------------------
    # Multi-frame clip search
    # ------------------------------------------------------------------

    def search_clip(
        self,
        image_paths: Iterable[Path],
        *,
        per_query_limit: int = 10,
        final_limit: int = 10,
    ) -> list[VisualClipResult]:
        """
        Search the archive using multiple query frames
        and return scene-level ranked results.
        """

        frame_results = self.search_frames(
            image_paths,
            per_query_limit=per_query_limit,
            final_limit=max(
                final_limit * 10,
                per_query_limit,
            ),
        )

        clip_results = (
            self.aggregate_results_by_scene(
                frame_results
            )
        )

        return clip_results[
            :final_limit
        ]