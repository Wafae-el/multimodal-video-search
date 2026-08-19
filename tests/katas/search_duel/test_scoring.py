from packages.retrieval.scoring import bm25_score, cosine_similarity, reciprocal_rank_fusion


def test_dense_sparse_and_fusion_rank_expected_items():
    assert cosine_similarity([1, 0], [1, 0]) > cosine_similarity([1, 0], [0, 1])
    corpus = [["ada", "lovelace"], ["poet", "math"]]
    assert bm25_score(["ada"], corpus[0], corpus) > bm25_score(["ada"], corpus[1], corpus)
    assert reciprocal_rank_fusion([["semantic", "exact"], ["exact", "other"]])[0][0] == "exact"
