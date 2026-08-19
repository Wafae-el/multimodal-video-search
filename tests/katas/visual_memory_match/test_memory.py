from packages.visual.memory import clip_pool_scores, suppress_duplicates


def test_clip_pool_and_duplicate_suppression():
    scores = clip_pool_scores([[1, 0], [0.8, 0.2]], {"match": [1, 0], "hard_negative": [0, 1]})
    assert scores[0][0] == "match"
    assert suppress_duplicates(["a1", "a2", "b"], [{"a1", "a2"}], 3) == ["a1", "b"]
