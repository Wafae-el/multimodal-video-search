from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class VisualSimilarity:
    """
    Similarity between one query frame and one archive frame.
    """

    query_index: int
    archive_index: int
    score: float


@dataclass
class ClipSimilarity:
    """
    Aggregated similarity for one video/scene clip.
    """

    clip_id: str
    score: float
    max_score: float
    top_r_mean: float
    matched_frames: list[int]


def l2_normalize(
    vectors: np.ndarray,
) -> np.ndarray:
    """
    L2-normalize vectors row-wise.

    Input:
        shape = (N, D)

    Output:
        shape = (N, D)
        every non-zero row has norm ~= 1.
    """

    vectors = np.asarray(
        vectors,
        dtype=np.float32,
    )

    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)

    if vectors.ndim != 2:
        raise ValueError(
            "vectors must have shape (N, D)"
        )

    norms = np.linalg.norm(
        vectors,
        axis=1,
        keepdims=True,
    )

    norms = np.clip(
        norms,
        1e-12,
        None,
    )

    return vectors / norms


def cosine_similarity_matrix(
    query_vectors: np.ndarray,
    archive_vectors: np.ndarray,
) -> np.ndarray:
    """
    Compute query-by-archive cosine similarity matrix.

    Result shape:
        (number_of_queries, number_of_archive_vectors)
    """

    queries = l2_normalize(
        query_vectors
    )

    archive = l2_normalize(
        archive_vectors
    )

    if queries.shape[1] != archive.shape[1]:
        raise ValueError(
            "Query and archive vectors must have "
            "the same dimension"
        )

    return queries @ archive.T


def top_k_similar(
    similarity_matrix: np.ndarray,
    k: int = 5,
) -> list[list[VisualSimilarity]]:
    """
    Return top-k archive frames for every query frame.
    """

    matrix = np.asarray(
        similarity_matrix,
        dtype=np.float32,
    )

    if matrix.ndim != 2:
        raise ValueError(
            "similarity_matrix must have shape (Q, A)"
        )

    if k <= 0:
        raise ValueError(
            "k must be greater than zero"
        )

    k = min(k, matrix.shape[1])

    results = []

    for query_index in range(matrix.shape[0]):

        scores = matrix[query_index]

        indices = np.argsort(
            scores
        )[::-1][:k]

        query_results = []

        for archive_index in indices:

            query_results.append(
                VisualSimilarity(
                    query_index=query_index,
                    archive_index=int(
                        archive_index
                    ),
                    score=float(
                        scores[archive_index]
                    ),
                )
            )

        results.append(
            query_results
        )

    return results


def suppress_duplicate_frames(
    matches: Iterable[VisualSimilarity],
    archive_frame_keys: list[str],
    threshold: float = 0.98,
) -> list[VisualSimilarity]:
    """
    Remove repeated archive frames.

    Two archive frames are considered duplicates when
    they share the same archive_frame_key.

    The highest-scoring occurrence is retained.
    """

    if threshold < 0 or threshold > 1:
        raise ValueError(
            "threshold must be between 0 and 1"
        )

    best_by_key: dict[
        str,
        VisualSimilarity,
    ] = {}

    for match in matches:

        if (
            match.archive_index < 0
            or match.archive_index
            >= len(archive_frame_keys)
        ):
            raise IndexError(
                "archive_index is outside archive_frame_keys"
            )

        key = archive_frame_keys[
            match.archive_index
        ]

        previous = best_by_key.get(key)

        if (
            previous is None
            or match.score > previous.score
        ):
            best_by_key[key] = match

    return sorted(
        best_by_key.values(),
        key=lambda item: item.score,
        reverse=True,
    )


def aggregate_clip_similarity(
    clip_id: str,
    frame_scores: Iterable[float],
    matched_frames: Iterable[int] | None = None,
    beta: float = 0.7,
    top_r: int = 3,
) -> ClipSimilarity:
    """
    Aggregate frame similarities into one clip score.

    S_clip =
        beta * max_similarity
        +
        (1 - beta) * mean(top-r similarities)
    """

    if not 0 <= beta <= 1:
        raise ValueError(
            "beta must be between 0 and 1"
        )

    if top_r <= 0:
        raise ValueError(
            "top_r must be greater than zero"
        )

    scores = np.asarray(
        list(frame_scores),
        dtype=np.float32,
    )

    if scores.size == 0:
        raise ValueError(
            "frame_scores cannot be empty"
        )

    scores = np.sort(
        scores
    )[::-1]

    max_score = float(
        scores[0]
    )

    selected = scores[
        : min(top_r, len(scores))
    ]

    top_r_mean = float(
        np.mean(selected)
    )

    clip_score = (
        beta * max_score
        + (1.0 - beta) * top_r_mean
    )

    if matched_frames is None:
        matched_frames = []

    return ClipSimilarity(
        clip_id=clip_id,
        score=float(clip_score),
        max_score=max_score,
        top_r_mean=top_r_mean,
        matched_frames=list(
            matched_frames
        ),
    )