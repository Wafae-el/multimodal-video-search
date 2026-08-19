from packages.fusion.ranking import Candidate, fuse_candidates, quality_weighted_rrf


def test_quality_weighted_rrf_keeps_single_channel_visible():
    scores = quality_weighted_rrf(
        {"visual": ["decoy", "multi"], "transcript": ["multi"]},
        {"visual": 0.5, "transcript": 0.5},
    )
    assert scores["multi"] > scores["decoy"]
    assert scores["decoy"] > 0


def test_fusion_merges_supporting_intervals_with_bounded_bonus():
    fused = fuse_candidates(
        {
            "visual": [Candidate("v1", "visual", 1, 1000, 2000, 0.8)],
            "transcript": [Candidate("t1", "transcript", 1, 1500, 2500, 0.7)],
            "audio": [Candidate("a_far", "audio", 1, 20000, 21000, 0.9)],
        },
        {"visual": 0.4, "transcript": 0.4, "audio": 0.2},
        max_gap_ms=500,
    )
    assert fused[0].start_ms == 1000
    assert fused[0].end_ms == 2500
    assert {e["modality"] for e in fused[0].evidence} == {"visual", "transcript"}
