from dataclasses import dataclass
from typing import Any


# ============================================================
# TEXT FUSION
# ============================================================


@dataclass(frozen=True)
class FusionResult:
    chunk_id: str
    score: float
    dense_rank: int | None
    sparse_rank: int | None


def reciprocal_rank_fusion(
    dense_results,
    sparse_results,
    k: int = 60,
    limit: int = 10,
) -> list[FusionResult]:

    scores: dict[str, float] = {}

    dense_ranks: dict[str, int] = {}
    sparse_ranks: dict[str, int] = {}

    # --------------------------------------------------------
    # DENSE
    # --------------------------------------------------------

    for result in dense_results:
        rank = result.rank
        chunk_id = result.chunk_id

        dense_ranks[chunk_id] = rank

        scores[chunk_id] = (
            scores.get(chunk_id, 0.0)
            + 1.0 / (k + rank)
        )

    # --------------------------------------------------------
    # SPARSE / BM25
    # --------------------------------------------------------

    for result in sparse_results:
        rank = result.rank
        chunk_id = result.chunk_id

        sparse_ranks[chunk_id] = rank

        scores[chunk_id] = (
            scores.get(chunk_id, 0.0)
            + 1.0 / (k + rank)
        )

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        FusionResult(
            chunk_id=chunk_id,
            score=score,
            dense_rank=dense_ranks.get(chunk_id),
            sparse_rank=sparse_ranks.get(chunk_id),
        )
        for chunk_id, score in ranked[:limit]
    ]


# ============================================================
# AUDIO AGGREGATION
# ============================================================


@dataclass(frozen=True)
class AggregatedAudioResult:
    result_id: str
    score: float

    start_ms: int
    end_ms: int

    quality_score: float

    window_count: int

    audio_ranks: tuple[int, ...]

    payload: dict[str, Any]


def aggregate_neighboring_audio_hits(
    audio_results,
    k: int = 60,
    max_gap_ms: int = 2500,
    limit: int = 10,
) -> list[AggregatedAudioResult]:
    """
    Aggregate neighboring audio windows.

    Windows are considered neighboring when the distance
    between the end of one window and the beginning of the
    next is <= max_gap_ms.

    Audio quality attenuates the contribution of each window.
    """

    if not audio_results:
        return []

    items = []

    for result in audio_results:

        payload = result.payload or {}

        start_ms = payload.get("start_ms")
        end_ms = payload.get("end_ms")

        if start_ms is None or end_ms is None:
            continue

        quality = payload.get(
            "quality_score"
        )

        if quality is None:
            quality = getattr(
                result,
                "quality_score",
                1.0,
            )

        quality = float(
            max(
                0.0,
                min(
                    1.0,
                    quality,
                ),
            )
        )

        items.append(
            {
                "result": result,
                "start_ms": int(start_ms),
                "end_ms": int(end_ms),
                "quality": quality,
            }
        )

    if not items:
        return []

    # --------------------------------------------------------
    # SORT BY TIMELINE
    # --------------------------------------------------------

    items.sort(
        key=lambda item: (
            item["start_ms"],
            item["end_ms"],
        )
    )

    # --------------------------------------------------------
    # GROUP NEIGHBORING WINDOWS
    # --------------------------------------------------------

    groups = []

    current_group = [items[0]]

    for item in items[1:]:

        previous = current_group[-1]

        gap = (
            item["start_ms"]
            - previous["end_ms"]
        )

        if gap <= max_gap_ms:
            current_group.append(item)
        else:
            groups.append(current_group)
            current_group = [item]

    groups.append(current_group)

    # --------------------------------------------------------
    # BUILD AGGREGATED RESULTS
    # --------------------------------------------------------

    aggregated = []

    for group in groups:

        if not group:
            continue

        first = group[0]
        last = group[-1]

        total_score = 0.0

        quality_weighted_score = 0.0
        quality_weight = 0.0

        ranks = []

        for item in group:

            result = item["result"]
            quality = item["quality"]

            base_score = (
                1.0
                / (
                    k + result.rank
                )
            )

            weighted_score = (
                base_score * quality
            )

            total_score += weighted_score

            quality_weighted_score += (
                quality * base_score
            )

            quality_weight += base_score

            ranks.append(result.rank)

        if quality_weight > 0:
            group_quality = (
                quality_weighted_score
                / quality_weight
            )
        else:
            group_quality = 0.0

        payload = dict(
            first["result"].payload or {}
        )

        payload.update(
            {
                "start_ms": first["start_ms"],
                "end_ms": last["end_ms"],
                "quality_score": float(
                    group_quality
                ),
                "window_count": len(group),
                "aggregated": True,
            }
        )

        # Stable identifier for the aggregated group.
        result_id = str(
            first["result"].point_id
        )

        aggregated.append(
            AggregatedAudioResult(
                result_id=result_id,
                score=float(total_score),
                start_ms=first["start_ms"],
                end_ms=last["end_ms"],
                quality_score=float(
                    group_quality
                ),
                window_count=len(group),
                audio_ranks=tuple(ranks),
                payload=payload,
            )
        )

    # --------------------------------------------------------
    # SORT BY SCORE
    # --------------------------------------------------------

    aggregated.sort(
        key=lambda result: result.score,
        reverse=True,
    )

    return aggregated[:limit]


# ============================================================
# TEMPORAL HELPERS
# ============================================================


def _get_time_range(
    result,
) -> tuple[int, int] | None:
    """
    Extract temporal information from a retrieval result.

    Supported formats:

    Text:
        payload.start_ms / payload.end_ms

    Audio:
        result.start_ms / result.end_ms

    Visual:
        payload.timestamp_ms
    """

    payload = getattr(
        result,
        "payload",
        None,
    ) or {}

    # --------------------------------------------------------
    # Explicit result timestamps
    # --------------------------------------------------------

    start_ms = getattr(
        result,
        "start_ms",
        None,
    )

    end_ms = getattr(
        result,
        "end_ms",
        None,
    )

    if (
        start_ms is not None
        and end_ms is not None
    ):
        return (
            int(start_ms),
            int(end_ms),
        )

    # --------------------------------------------------------
    # Payload timestamps
    # --------------------------------------------------------

    start_ms = payload.get(
        "start_ms"
    )

    end_ms = payload.get(
        "end_ms"
    )

    if (
        start_ms is not None
        and end_ms is not None
    ):
        return (
            int(start_ms),
            int(end_ms),
        )

    # --------------------------------------------------------
    # Visual frame
    # --------------------------------------------------------

    timestamp_ms = payload.get(
        "timestamp_ms"
    )

    if timestamp_ms is not None:
        timestamp_ms = int(
            timestamp_ms
        )

        return (
            timestamp_ms,
            timestamp_ms,
        )

    return None


def _get_video_id(
    result,
) -> int | None:

    payload = getattr(
        result,
        "payload",
        None,
    ) or {}

    video_id = payload.get(
        "video_id"
    )

    if video_id is None:
        return None

    try:
        return int(video_id)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _interval_overlap(
    range_a: tuple[int, int],
    range_b: tuple[int, int],
) -> int:

    start = max(
        range_a[0],
        range_b[0],
    )

    end = min(
        range_a[1],
        range_b[1],
    )

    return max(
        0,
        end - start,
    )


def _temporal_distance(
    range_a: tuple[int, int],
    range_b: tuple[int, int],
) -> int:

    if _interval_overlap(
        range_a,
        range_b,
    ) > 0:
        return 0

    if range_a[1] < range_b[0]:
        return (
            range_b[0]
            - range_a[1]
        )

    return (
        range_a[0]
        - range_b[1]
    )


def _temporally_related(
    result_a,
    result_b,
    max_distance_ms: int = 5000,
) -> bool:
    """
    Determine whether two retrieval results refer to
    approximately the same temporal region of the same video.
    """

    video_a = _get_video_id(
        result_a
    )

    video_b = _get_video_id(
        result_b
    )

    if (
        video_a is None
        or video_b is None
    ):
        return False

    if video_a != video_b:
        return False

    range_a = _get_time_range(
        result_a
    )

    range_b = _get_time_range(
        result_b
    )

    if (
        range_a is None
        or range_b is None
    ):
        return False

    distance = _temporal_distance(
        range_a,
        range_b,
    )

    return distance <= max_distance_ms


def _result_time(
    result,
) -> tuple[int, int] | None:

    return _get_time_range(
        result
    )


# ============================================================
# MULTIMODAL FUSION
# ============================================================


@dataclass(frozen=True)
class MultimodalFusionResult:
    result_id: str
    score: float

    text_rank: int | None
    audio_rank: int | None
    visual_rank: int | None

    payload: dict[str, Any]


def multimodal_reciprocal_rank_fusion(
    text_results=None,
    audio_results=None,
    visual_results=None,
    k: int = 60,
    limit: int = 10,
    text_weight: float = 1.0,
    audio_weight: float = 1.0,
    visual_weight: float = 1.0,
    temporal_tolerance_ms: int = 5000,
) -> list[MultimodalFusionResult]:
    """
    Quality-aware temporal multimodal fusion.

    Results from different modalities are associated when:

        1. They belong to the same video.
        2. Their temporal regions overlap or are close enough.

    Audio contribution is additionally weighted by audio quality.

    A canonical multimodal result is created around the strongest
    available textual result. Audio and visual evidence that falls
    inside the temporal neighborhood contributes to that result.

    Unmatched audio/visual results are also retained so that a modality
    cannot disappear completely from retrieval.
    """

    text_results = text_results or []
    audio_results = audio_results or []
    visual_results = visual_results or []

    # --------------------------------------------------------
    # MODALITY QUALITY
    # --------------------------------------------------------

    modality_quality = {
        "text": 1.0 if text_results else 0.0,
        "audio": 0.0,
        "visual": 1.0 if visual_results else 0.0,
    }

    if audio_results:

        quality_values = []

        for result in audio_results:

            quality = getattr(
                result,
                "quality_score",
                None,
            )

            if quality is None:
                payload = (
                    result.payload or {}
                )

                quality = payload.get(
                    "quality_score"
                )

            if quality is not None:

                quality_values.append(
                    float(
                        max(
                            0.0,
                            min(
                                1.0,
                                quality,
                            ),
                        )
                    )
                )

        if quality_values:

            modality_quality["audio"] = (
                sum(quality_values)
                / len(quality_values)
            )

        else:
            modality_quality["audio"] = 1.0

    # --------------------------------------------------------
    # MODALITY WEIGHTS
    # --------------------------------------------------------

    weighted_modalities = {
        "text": (
            text_weight
            * modality_quality["text"]
        ),
        "audio": (
            audio_weight
            * modality_quality["audio"]
        ),
        "visual": (
            visual_weight
            * modality_quality["visual"]
        ),
    }

    denominator = sum(
        weighted_modalities.values()
    )

    if denominator > 0:

        normalized_weights = {
            modality: value / denominator
            for modality, value
            in weighted_modalities.items()
        }

    else:

        normalized_weights = {
            "text": 0.0,
            "audio": 0.0,
            "visual": 0.0,
        }

    # --------------------------------------------------------
    # INTERNAL STORAGE
    # --------------------------------------------------------

    candidates = []

    used_audio = set()
    used_visual = set()

    # --------------------------------------------------------
    # TEXT-CENTERED MULTIMODAL RESULTS
    # --------------------------------------------------------

    for text_rank, text_result in enumerate(
        text_results,
        start=1,
    ):

        text_payload = (
            text_result.payload or {}
        )

        text_id = str(
            text_result.chunk_id
        )

        text_range = _result_time(
            text_result
        )

        text_video_id = _get_video_id(
            text_result
        )

        score = (
            normalized_weights["text"]
            * 1.0
            / (k + text_rank)
        )

        matched_audio = []
        matched_visual = []

        # ----------------------------------------------------
        # AUDIO MATCHES
        # ----------------------------------------------------

        for audio_rank, audio_result in enumerate(
            audio_results,
            start=1,
        ):

            if _temporally_related(
                text_result,
                audio_result,
                max_distance_ms=temporal_tolerance_ms,
            ):

                quality = getattr(
                    audio_result,
                    "quality_score",
                    None,
                )

                if quality is None:

                    audio_payload = (
                        audio_result.payload or {}
                    )

                    quality = audio_payload.get(
                        "quality_score",
                        1.0,
                    )

                quality = float(
                    max(
                        0.0,
                        min(
                            1.0,
                            quality,
                        ),
                    )
                )

                contribution = (
                    normalized_weights["audio"]
                    * quality
                    / (k + audio_rank)
                )

                score += contribution

                matched_audio.append(
                    {
                        "rank": audio_rank,
                        "result": audio_result,
                        "quality": quality,
                    }
                )

                used_audio.add(
                    audio_rank
                )

        # ----------------------------------------------------
        # VISUAL MATCHES
        # ----------------------------------------------------

        for visual_rank, visual_result in enumerate(
            visual_results,
            start=1,
        ):

            if _temporally_related(
                text_result,
                visual_result,
                max_distance_ms=temporal_tolerance_ms,
            ):

                contribution = (
                    normalized_weights["visual"]
                    / (k + visual_rank)
                )

                score += contribution

                matched_visual.append(
                    {
                        "rank": visual_rank,
                        "result": visual_result,
                    }
                )

                used_visual.add(
                    visual_rank
                )

        # ----------------------------------------------------
        # BUILD PAYLOAD
        # ----------------------------------------------------

        payload = dict(
            text_payload
        )

        payload["fusion_weights"] = {
            "text": normalized_weights["text"],
            "audio": normalized_weights["audio"],
            "visual": normalized_weights["visual"],
        }

        payload["modality_quality"] = {
            "text": modality_quality["text"],
            "audio": modality_quality["audio"],
            "visual": modality_quality["visual"],
        }

        payload["temporal_fusion"] = True

        payload["matched_audio_count"] = len(
            matched_audio
        )

        payload["matched_visual_count"] = len(
            matched_visual
        )

        payload["audio_evidence"] = [
            {
                "rank": item["rank"],
                "start_ms": getattr(
                    item["result"],
                    "start_ms",
                    item["result"].payload.get(
                        "start_ms"
                    ),
                ),
                "end_ms": getattr(
                    item["result"],
                    "end_ms",
                    item["result"].payload.get(
                        "end_ms"
                    ),
                ),
                "quality_score": item["quality"],
            }
            for item in matched_audio
        ]

        payload["visual_evidence"] = [
            {
                "rank": item["rank"],
                "timestamp_ms": (
                    item["result"].payload or {}
                ).get(
                    "timestamp_ms"
                ),
            }
            for item in matched_visual
        ]

        candidates.append(
            MultimodalFusionResult(
                result_id=text_id,
                score=float(score),
                text_rank=text_rank,
                audio_rank=(
                    min(
                        (
                            item["rank"]
                            for item in matched_audio
                        ),
                        default=None,
                    )
                ),
                visual_rank=(
                    min(
                        (
                            item["rank"]
                            for item in matched_visual
                        ),
                        default=None,
                    )
                ),
                payload=payload,
            )
        )

    # --------------------------------------------------------
    # UNMATCHED AUDIO RESULTS
    # --------------------------------------------------------

    for audio_rank, audio_result in enumerate(
        audio_results,
        start=1,
    ):

        if audio_rank in used_audio:
            continue

        result_id = str(
            audio_result.result_id
        )

        payload = dict(
            audio_result.payload or {}
        )

        quality = float(
            max(
                0.0,
                min(
                    1.0,
                    getattr(
                        audio_result,
                        "quality_score",
                        payload.get(
                            "quality_score",
                            1.0,
                        ),
                    ),
                ),
            )
        )

        score = (
            normalized_weights["audio"]
            * quality
            / (k + audio_rank)
        )

        payload["fusion_weights"] = {
            "text": normalized_weights["text"],
            "audio": normalized_weights["audio"],
            "visual": normalized_weights["visual"],
        }

        payload["modality_quality"] = {
            "text": modality_quality["text"],
            "audio": modality_quality["audio"],
            "visual": modality_quality["visual"],
        }

        payload["temporal_fusion"] = True

        candidates.append(
            MultimodalFusionResult(
                result_id=result_id,
                score=float(score),
                text_rank=None,
                audio_rank=audio_rank,
                visual_rank=None,
                payload=payload,
            )
        )

    # --------------------------------------------------------
    # UNMATCHED VISUAL RESULTS
    # --------------------------------------------------------

    for visual_rank, visual_result in enumerate(
        visual_results,
        start=1,
    ):

        if visual_rank in used_visual:
            continue

        result_id = str(
            visual_result.point_id
        )

        payload = dict(
            visual_result.payload or {}
        )

        score = (
            normalized_weights["visual"]
            / (k + visual_rank)
        )

        payload["fusion_weights"] = {
            "text": normalized_weights["text"],
            "audio": normalized_weights["audio"],
            "visual": normalized_weights["visual"],
        }

        payload["modality_quality"] = {
            "text": modality_quality["text"],
            "audio": modality_quality["audio"],
            "visual": modality_quality["visual"],
        }

        payload["temporal_fusion"] = True

        candidates.append(
            MultimodalFusionResult(
                result_id=result_id,
                score=float(score),
                text_rank=None,
                audio_rank=None,
                visual_rank=visual_rank,
                payload=payload,
            )
        )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    candidates.sort(
        key=lambda result: result.score,
        reverse=True,
    )

    return candidates[:limit]