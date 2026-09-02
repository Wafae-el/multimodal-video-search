import numpy as np

from packages.visual.similarity import (
    aggregate_clip_similarity,
    cosine_similarity_matrix,
    l2_normalize,
    suppress_duplicate_frames,
    top_k_similar,
    VisualSimilarity,
)


def main():

    print("=" * 70)
    print("WEEK 4 - VISUAL MEMORY MATCH")
    print("=" * 70)

    # ------------------------------------------------------------
    # 1. L2 normalization
    # ------------------------------------------------------------

    vectors = np.array(
        [
            [3.0, 4.0],
            [1.0, 0.0],
        ],
        dtype=np.float32,
    )

    normalized = l2_normalize(
        vectors
    )

    norms = np.linalg.norm(
        normalized,
        axis=1,
    )

    assert np.allclose(
        norms,
        1.0,
        atol=1e-5,
    )

    print("PASS: L2 normalization")

    # ------------------------------------------------------------
    # 2. Query/archive vectors
    # ------------------------------------------------------------

    query_vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )

    archive_vectors = np.array(
        [
            [1.0, 0.0, 0.0],  # correct scene
            [0.99, 0.01, 0.0],  # duplicate
            [0.0, 1.0, 0.0],  # second scene
            [0.0, 0.0, 1.0],  # hard negative
        ],
        dtype=np.float32,
    )

    # ------------------------------------------------------------
    # 3. Similarity matrix
    # ------------------------------------------------------------

    matrix = cosine_similarity_matrix(
        query_vectors,
        archive_vectors,
    )

    print(
        "SIMILARITY MATRIX SHAPE =",
        matrix.shape,
    )

    print(
        "SIMILARITY MATRIX ="
    )

    print(matrix)

    assert matrix.shape == (
        2,
        4,
    )

    assert matrix[0, 0] > 0.99

    print(
        "PASS: Query-by-archive cosine matrix"
    )

    # ------------------------------------------------------------
    # 4. Top-K
    # ------------------------------------------------------------

    top_results = top_k_similar(
        matrix,
        k=3,
    )

    assert len(top_results) == 2

    assert (
        top_results[0][0].archive_index
        == 0
    )

    print(
        "PASS: Top-K visual retrieval"
    )

    # ------------------------------------------------------------
    # 5. Duplicate suppression
    # ------------------------------------------------------------

    matches = [
        VisualSimilarity(
            query_index=0,
            archive_index=0,
            score=1.0,
        ),
        VisualSimilarity(
            query_index=0,
            archive_index=1,
            score=0.995,
        ),
        VisualSimilarity(
            query_index=0,
            archive_index=2,
            score=0.82,
        ),
    ]

    archive_frame_keys = [
        "scene_4",
        "scene_4",
        "scene_5",
    ]

    filtered = suppress_duplicate_frames(
        matches,
        archive_frame_keys,
    )

    print(
        "MATCHES BEFORE DUPLICATE SUPPRESSION =",
        len(matches),
    )

    print(
        "MATCHES AFTER DUPLICATE SUPPRESSION =",
        len(filtered),
    )

    assert len(filtered) == 2

    assert filtered[0].archive_index == 0

    print(
        "PASS: Duplicate suppression"
    )

    # ------------------------------------------------------------
    # 6. Clip aggregation
    # ------------------------------------------------------------

    clip = aggregate_clip_similarity(
        clip_id="scene_4",
        frame_scores=[
            1.0,
            0.90,
            0.80,
            0.30,
        ],
        matched_frames=[
            0,
            1,
            2,
            3,
        ],
        beta=0.7,
        top_r=3,
    )

    print(
        "MAX SCORE =",
        clip.max_score,
    )

    print(
        "TOP-R MEAN =",
        clip.top_r_mean,
    )

    print(
        "CLIP SCORE =",
        clip.score,
    )

    expected_top_r_mean = (
        1.0 + 0.90 + 0.80
    ) / 3

    expected_score = (
        0.7 * 1.0
        + 0.3 * expected_top_r_mean
    )

    assert np.isclose(
        clip.top_r_mean,
        expected_top_r_mean,
        atol=1e-6,
    )

    assert np.isclose(
        clip.score,
        expected_score,
        atol=1e-6,
    )

    print(
        "PASS: Max + top-r mean clip pooling"
    )

    # ------------------------------------------------------------
    # 7. Final validation
    # ------------------------------------------------------------

    assert (
        clip.score > 0.9
    )

    print(
        "PASS: Correct scene ranks first"
    )

    print()
    print("=" * 70)
    print("VISUAL MEMORY MATCH = PASS")
    print("=" * 70)


def test_visual_memory_match():
    main()


if __name__ == "__main__":
    main()