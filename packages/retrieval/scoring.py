import math
from collections import Counter
from collections.abc import Iterable

Vector = list[float]


def l2_normalize(vector: Iterable[float]) -> Vector:
    values = [float(v) for v in vector]
    norm = math.sqrt(sum(v * v for v in values))
    return [0.0 for _ in values] if norm == 0 else [v / norm for v in values]


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    av = l2_normalize(a)
    bv = l2_normalize(b)
    if len(av) != len(bv):
        raise ValueError("vectors must have the same length")
    return sum(x * y for x, y in zip(av, bv, strict=True))


def bm25_score(
    query_terms: list[str],
    document_terms: list[str],
    corpus: list[list[str]],
    k1: float = 1.2,
    b: float = 0.75,
) -> float:
    tf = Counter(document_terms)
    doc_len = len(document_terms) or 1
    avg_len = sum(len(doc) for doc in corpus) / max(1, len(corpus)) or 1
    score = 0.0
    for term in query_terms:
        df = sum(1 for doc in corpus if term in doc)
        if df == 0:
            continue
        idf = math.log(1 + (len(corpus) - df + 0.5) / (df + 0.5))
        freq = tf[term]
        score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * doc_len / avg_len))
    return score


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
