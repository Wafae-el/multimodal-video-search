import math

from packages.segmentation.timeline import Interval, interval_iou


def precision_at_k(relevant: set[str], ranked_ids: list[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    return len(relevant.intersection(ranked_ids[:k])) / k


def recall_at_k(relevant: set[str], ranked_ids: list[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(relevant.intersection(ranked_ids[:k])) / len(relevant)


def mean_reciprocal_rank(relevant: set[str], ranked_ids: list[str]) -> float:
    for rank, item_id in enumerate(ranked_ids, start=1):
        if item_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(gains: dict[str, float], ranked_ids: list[str], k: int) -> float:
    def dcg(ids: list[str]) -> float:
        return sum(
            gains.get(item_id, 0.0) / math.log2(rank + 1)
            for rank, item_id in enumerate(ids, start=1)
        )

    ideal = sorted(gains, key=lambda item_id: gains[item_id], reverse=True)[:k]
    denom = dcg(ideal)
    return 0.0 if denom == 0 else dcg(ranked_ids[:k]) / denom


def temporal_iou_at_threshold(predicted: Interval, truth: Interval, threshold: float = 0.5) -> bool:
    return interval_iou(predicted, truth) >= threshold
