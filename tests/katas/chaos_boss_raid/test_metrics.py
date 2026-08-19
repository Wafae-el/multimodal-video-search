from packages.evaluation.metrics import mean_reciprocal_rank, ndcg_at_k, precision_at_k, recall_at_k, temporal_iou_at_threshold
from packages.segmentation.timeline import Interval


def test_retrieval_metrics_and_temporal_iou():
    ranked = ["miss", "hit", "other"]
    assert precision_at_k({"hit"}, ranked, 2) == 0.5
    assert recall_at_k({"hit"}, ranked, 2) == 1.0
    assert mean_reciprocal_rank({"hit"}, ranked) == 0.5
    assert ndcg_at_k({"hit": 3, "other": 1}, ranked, 3) > 0
    assert temporal_iou_at_threshold(Interval(0, 1000), Interval(250, 1000), 0.7)
