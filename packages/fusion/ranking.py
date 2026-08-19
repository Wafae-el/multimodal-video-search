from dataclasses import dataclass, field

from packages.segmentation.timeline import Interval, interval_iou, merge_intervals


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    modality: str
    rank: int
    start_ms: int
    end_ms: int
    score: float | None = None
    evidence: dict[str, str] = field(default_factory=dict)

    @property
    def interval(self) -> Interval:
        return Interval(self.start_ms, self.end_ms, self.candidate_id)


@dataclass(frozen=True)
class FusedResult:
    result_id: str
    start_ms: int
    end_ms: int
    final_score: float
    channel_scores: dict[str, float]
    evidence: list[dict[str, str]]


def normalize_active_weights(
    weights: dict[str, float], active_modalities: set[str]
) -> dict[str, float]:
    if any(weight < 0 for weight in weights.values()):
        raise ValueError("weights must be non-negative")
    total = sum(weight for modality, weight in weights.items() if modality in active_modalities)
    if total <= 0:
        raise ValueError("at least one active modality must have positive weight")
    return {
        modality: (weight / total if modality in active_modalities else 0.0)
        for modality, weight in weights.items()
    }


def quality_weighted_rrf(
    rankings: dict[str, list[str]],
    weights: dict[str, float],
    qualities: dict[str, float] | None = None,
    k: int = 60,
) -> dict[str, float]:
    active = {modality for modality, ranking in rankings.items() if ranking}
    normalized = normalize_active_weights(weights, active)
    qualities = qualities or {}
    scores: dict[str, float] = {}
    for modality, ranking in rankings.items():
        multiplier = normalized.get(modality, 0.0) * qualities.get(modality, 1.0)
        if multiplier == 0:
            continue
        for rank, candidate_id in enumerate(ranking, start=1):
            scores[candidate_id] = scores.get(candidate_id, 0.0) + multiplier / (k + rank)
    return scores


def rerank_exact_cosine(candidates: list[Candidate]) -> list[Candidate]:
    return sorted(
        candidates,
        key=lambda item: (
            -(item.score if item.score is not None else 0.0),
            item.rank,
            item.candidate_id,
        ),
    )


def merge_supporting_intervals(
    candidates: list[Candidate],
    *,
    max_gap_ms: int = 1000,
    min_iou: float = 0.1,
) -> list[list[Candidate]]:
    groups: list[list[Candidate]] = []
    for candidate in sorted(candidates, key=lambda item: (item.start_ms, item.end_ms)):
        placed = False
        for group in groups:
            group_interval = merge_intervals(
                [member.interval for member in group], max_gap_ms=max_gap_ms
            )[0]
            close = candidate.start_ms <= group_interval.end_ms + max_gap_ms
            overlaps = interval_iou(candidate.interval, group_interval) >= min_iou
            if close or overlaps:
                group.append(candidate)
                placed = True
                break
        if not placed:
            groups.append([candidate])
    return groups


def fuse_candidates(
    candidates_by_modality: dict[str, list[Candidate]],
    weights: dict[str, float],
    qualities: dict[str, float] | None = None,
    *,
    support_bonus: float = 0.05,
    max_gap_ms: int = 1000,
) -> list[FusedResult]:
    rankings = {
        modality: [candidate.candidate_id for candidate in rerank_exact_cosine(candidates)]
        for modality, candidates in candidates_by_modality.items()
    }
    rrf_scores = quality_weighted_rrf(rankings, weights, qualities)
    all_candidates = [
        candidate for candidates in candidates_by_modality.values() for candidate in candidates
    ]
    results: list[FusedResult] = []
    for group in merge_supporting_intervals(all_candidates, max_gap_ms=max_gap_ms):
        intervals = merge_intervals(
            [candidate.interval for candidate in group], max_gap_ms=max_gap_ms
        )
        result_id = min(candidate.candidate_id for candidate in group)
        modalities = {candidate.modality for candidate in group}
        base_score = max(rrf_scores.get(candidate.candidate_id, 0.0) for candidate in group)
        bonus = min(support_bonus, support_bonus * max(0, len(modalities) - 1))
        channel_scores = {
            modality: sum(
                rrf_scores.get(candidate.candidate_id, 0.0)
                for candidate in group
                if candidate.modality == modality
            )
            for modality in sorted(modalities)
        }
        results.append(
            FusedResult(
                result_id=result_id,
                start_ms=intervals[0].start_ms,
                end_ms=intervals[-1].end_ms,
                final_score=base_score + bonus,
                channel_scores=channel_scores,
                evidence=[
                    candidate.evidence | {"modality": candidate.modality} for candidate in group
                ],
            )
        )
    return sorted(results, key=lambda item: (-item.final_score, item.start_ms, item.result_id))
