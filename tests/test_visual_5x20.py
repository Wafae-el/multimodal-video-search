from __future__ import annotations

import numpy as np

from packages.visual.similarity import (
    cosine_similarity_matrix,
    l2_normalize,
    suppress_duplicate_frames,
    top_k_similar,
)


def main():

    print("=" * 70)
    print("WEEK 4 - VISUAL 5x20 VALIDATION")
    print("=" * 70)

    # ------------------------------------------------------------
    # 1. Create deterministic query/archive embeddings
    # ------------------------------------------------------------
    #
    # 5 query frames
    # 20 archive frames
    #
    # Each query has one clearly matching archive frame.
    # Additional archive frames act as negatives.
    # Some archive entries intentionally share the same
    # archive-frame key to test duplicate suppression.
    # ------------------------------------------------------------

    query_vectors = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [0.7, 0.7, 0.0, 0.0],
        ],
        dtype=np.float32,
    )

    archive_vectors = np.array(
        [
            # Strong match for query 0
            [1.0, 0.0, 0.0, 0.0],

            # Strong match for query 1
            [0.0, 1.0, 0.0, 0.0],

            # Strong match for query 2
            [0.0, 0.0, 1.0, 0.0],

            # Strong match for query 3
            [0.0, 0.0, 0.0, 1.0],

            # Strong match for query 4
            [0.7, 0.7, 0.0, 0.0],

            # Hard negatives
            [0.99, 0.05, 0.0, 0.0],
            [0.05, 0.99, 0.0, 0.0],
            [0.0, 0.05, 0.99, 0.0],
            [0.0, 0.0, 0.05, 0.99],
            [0.65, 0.70, 0.0, 0.0],

            # More negatives
            [0.5, 0.5, 0.0, 0.0],
            [0.5, 0.0, 0.5, 0.0],
            [0.5, 0.0, 0.0, 0.5],
            [0.0, 0.5, 0.5, 0.0],
            [0.0, 0.5, 0.0, 0.5],
            [0.0, 0.0, 0.5, 0.5],

            [0.2, 0.2, 0.2, 0.2],
            [-0.5, 0.5, 0.0, 0.0],
            [0.0, -0.5, 0.5, 0.0],
            [0.0, 0.0, -0.5, 0.5],
        ],
        dtype=np.float32,
    )

    assert query_vectors.shape == (5, 4)
    assert archive_vectors.shape == (20, 4)

    print("PASS: 5 query frames")
    print("PASS: 20 archive frames")

    # ------------------------------------------------------------
    # 2. L2 normalization
    # ------------------------------------------------------------

    normalized_queries = l2_normalize(
        query_vectors
    )

    normalized_archive = l2_normalize(
        archive_vectors
    )

    query_norms = np.linalg.norm(
        normalized_queries,
        axis=1,
    )

    archive_norms = np.linalg.norm(
        normalized_archive,
        axis=1,
    )

    assert np.allclose(
        query_norms,
        1.0,
        atol=1e-5,
    )

    assert np.allclose(
        archive_norms,
        1.0,
        atol=1e-5,
    )

    print("PASS: L2 normalization")

    # ------------------------------------------------------------
    # 3. Query x archive similarity matrix
    # ------------------------------------------------------------

    similarity_matrix = cosine_similarity_matrix(
        query_vectors,
        archive_vectors,
    )

    print(
        "SIMILARITY MATRIX SHAPE =",
        similarity_matrix.shape,
    )

    print("SIMILARITY MATRIX =")
    print(
        np.round(
            similarity_matrix,
            4,
        )
    )

    assert similarity_matrix.shape == (
        5,
        20,
    )

    print("PASS: 5x20 cosine similarity matrix")

    # ------------------------------------------------------------
    # 4. Top-K retrieval
    # ------------------------------------------------------------

    top_k = top_k_similar(
        similarity_matrix,
        k=5,
    )

    assert len(top_k) == 5

    for query_results in top_k:
        assert len(query_results) == 5

    print("PASS: Top-K retrieval for all 5 queries")

    # Expected strongest archive match:
    #
    # query 0 -> archive 0
    # query 1 -> archive 1
    # query 2 -> archive 2
    # query 3 -> archive 3
    # query 4 -> archive 4
    #

    expected_matches = [
        0,
        1,
        2,
        3,
        4,
    ]

    for query_index, expected_archive in enumerate(
        expected_matches
    ):

        best = top_k[query_index][0]

        print(
            f"QUERY {query_index} -> "
            f"ARCHIVE {best.archive_index} "
            f"SCORE={best.score:.4f}"
        )

        assert (
            best.archive_index
            == expected_archive
        )

    print("PASS: Correct archive frame first")

    # ------------------------------------------------------------
    # 5. Duplicate suppression
    # ------------------------------------------------------------

    # Simulate repeated archive frames.
    #
    # Archive 0 and archive 5 represent the same
    # logical frame key.
    #
    # Archive 1 and archive 6 represent another duplicate.
    #

    archive_frame_keys = [
        "video10-scene4-frame0",
        "video10-scene4-frame1",
        "video10-scene4-frame2",
        "video10-scene4-frame3",
        "video10-scene4-frame4",
        "video10-scene4-frame0",
        "video10-scene4-frame1",
        "video10-scene4-frame7",
        "video10-scene4-frame8",
        "video10-scene4-frame9",
        "video10-scene4-frame10",
        "video10-scene4-frame11",
        "video10-scene4-frame12",
        "video10-scene4-frame13",
        "video10-scene4-frame14",
        "video10-scene4-frame15",
        "video10-scene4-frame16",
        "video10-scene4-frame17",
        "video10-scene4-frame18",
        "video10-scene4-frame19",
    ]

    matches = []

    # Take the strongest result from every query.
    for query_results in top_k:
        matches.append(
            query_results[0]
        )

    # Add explicit duplicate matches.
    matches.append(
        type(matches[0])(
            query_index=0,
            archive_index=5,
            score=0.95,
        )
    )

    matches.append(
        type(matches[0])(
            query_index=1,
            archive_index=6,
            score=0.94,
        )
    )

    before = len(matches)

    deduplicated = suppress_duplicate_frames(
        matches,
        archive_frame_keys,
        threshold=0.98,
    )

    after = len(deduplicated)

    print(
        "MATCHES BEFORE DUPLICATE SUPPRESSION =",
        before,
    )

    print(
        "MATCHES AFTER DUPLICATE SUPPRESSION =",
        after,
    )

    assert after < before

    print("PASS: Duplicate suppression")

    # ------------------------------------------------------------
    # 6. Hard-negative validation
    # ------------------------------------------------------------

    # The hard negatives are intentionally close to the
    # corresponding query vectors, but the exact match
    # must remain ranked first.

    for query_index, expected_archive in enumerate(
        expected_matches
    ):

        best = top_k[query_index][0]

        assert (
            best.archive_index
            == expected_archive
        )

    print("PASS: Hard negatives do not beat exact matches")

    # ------------------------------------------------------------
    # 7. Final 5x20 validation
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("5 QUERY FRAMES x 20 ARCHIVE FRAMES = PASS")
    print("DUPLICATES + HARD NEGATIVES = PASS")
    print("CORRECT MATCH RANKING = PASS")
    print("=" * 70)


def test_visual_5x20():
    main()


if __name__ == "__main__":
    main()