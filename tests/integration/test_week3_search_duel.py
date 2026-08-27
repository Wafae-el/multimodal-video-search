from packages.retrieval.service import HybridRetrievalService


def check(condition, message):
    if not condition:
        raise AssertionError(f"FAIL: {message}")
    print(f"PASS: {message}")


def main():
    print("=" * 70)
    print("CODING QUEST 3 - SEARCH DUEL")
    print("=" * 70)

    retrieval = HybridRetrievalService(
        qdrant_url="http://qdrant:6333",
    )

    # Mini-corpus containing:
    # - proper name
    # - acronym
    # - number
    # - exact quotation
    # - paraphrase
    corpus = [
        "Josh Starmer explains cross-validation for machine learning.",
        "ASR means Automatic Speech Recognition in this video.",
        "The dataset contains 75 percent of the original samples.",
        "The speaker says: cross-validation helps evaluate models on unseen data.",
        "Cross-validation evaluates a model using data that was not used for training.",
        "Heart disease can be predicted using chest pain and blood circulation.",
    ]

    # Build lightweight chunks compatible with the retrieval service.
    class TestChunk:
        def __init__(self, chunk_id, text):
            self.chunk_id = chunk_id
            self.start_ms = 0
            self.end_ms = 10000
            self.text = text
            self.normalized_text = text.lower()
            self.source_segment_ids = [0]
            self.confidence = 0.0
            self.language = "en"

    chunks = [
        TestChunk(f"quest-{i:03d}", text)
        for i, text in enumerate(corpus)
    ]

    retrieval.index(
        chunks=chunks,
        video_id=999,
        language="en",
    )

    print()
    print("INDEXING = OK")

    # ================================================================
    # EXACT QUERIES
    # ================================================================

    exact_tests = [
        (
            "Josh Starmer",
            "Josh Starmer",
            "proper name",
        ),
        (
            "ASR",
            "ASR",
            "acronym",
        ),
        (
            "75 percent",
            "75 percent",
            "number",
        ),
        (
            "cross-validation helps evaluate models on unseen data",
            "cross-validation helps evaluate models on unseen data",
            "exact quotation",
        ),
    ]

    print()
    print("=" * 70)
    print("EXACT SEARCH")
    print("=" * 70)

    for query, expected, label in exact_tests:
        result = retrieval.search(query, limit=3)

        check(
            len(result["fused"]) > 0,
            f"{label}: results available",
        )

        relevant = False

        for item in result["fused"]:
            for chunk in chunks:
                if chunk.chunk_id == item.chunk_id:
                    if expected.lower() in chunk.normalized_text:
                        relevant = True

        check(
            relevant,
            f"{label}: relevant result in Top-3",
        )

        print(
            f"  QUERY: {query}"
        )

    # ================================================================
    # PARAPHRASE
    # ================================================================

    print()
    print("=" * 70)
    print("PARAPHRASE SEARCH")
    print("=" * 70)

    paraphrase_tests = [
        (
            "How can we test a machine learning model with data it has never seen?",
            "cross-validation",
            "cross-validation paraphrase",
        ),
    ]

    for query, expected, label in paraphrase_tests:
        result = retrieval.search(query, limit=3)

        check(
            len(result["fused"]) > 0,
            f"{label}: results available",
        )

        top_ids = [
            item.chunk_id
            for item in result["fused"]
        ]

        relevant = False

        for item in result["fused"]:
            for chunk in chunks:
                if chunk.chunk_id == item.chunk_id:
                    if expected.lower() in chunk.normalized_text:
                        relevant = True

        check(
            relevant,
            f"{label}: relevant result in Top-3",
        )

        print(
            f"  QUERY: {query}"
        )
        print(
            f"  TOP-3: {top_ids}"
        )

    # ================================================================
    # DENSE + BM25 + RRF
    # ================================================================

    result = retrieval.search(
        "cross-validation",
        limit=3,
    )

    check(
        len(result["dense"]) == 3,
        "Dense Top-3",
    )

    check(
        len(result["sparse"]) == 3,
        "BM25 Top-3",
    )

    check(
        len(result["fused"]) > 0,
        "RRF fusion",
    )

    print()
    print("=" * 70)
    print("CODING QUEST 3 - SEARCH DUEL = PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()