import numpy as np

from packages.audio.windowing import (
    AudioWindowGenerator,
)
from packages.retrieval.audio_qdrant_store import (
    AudioQdrantStore,
)


VIDEO_ID = 10


def main():

    print("=" * 70)
    print("WEEK 5 - AUDIO QDRANT")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. Generate audio windows
    # ---------------------------------------------------------

    generator = AudioWindowGenerator(
        window_ms=5000,
        overlap_ms=2500,
    )

    windows = generator.generate(
        duration_ms=15000
    )

    print(
        "WINDOWS =",
        len(windows),
    )

    assert len(windows) == 5

    print(
        "PASS: Audio windows"
    )

    # ---------------------------------------------------------
    # 2. Create deterministic test embeddings
    # ---------------------------------------------------------

    embeddings = []

    for index in range(
        len(windows)
    ):

        vector = np.zeros(
            512,
            dtype=np.float32,
        )

        vector[index] = 1.0

        embeddings.append(
            vector
        )

    print(
        "EMBEDDINGS =",
        len(embeddings),
    )

    print(
        "DIMENSION =",
        embeddings[0].shape[0],
    )

    assert len(embeddings) == 5
    assert embeddings[0].shape[0] == 512

    print(
        "PASS: Test embeddings"
    )

    # ---------------------------------------------------------
    # 3. Create Qdrant collection
    # ---------------------------------------------------------

    store = AudioQdrantStore(
        url="http://qdrant:6333",
    )

    store.create_collection()

    print(
        "PASS: Audio collection"
    )

    # ---------------------------------------------------------
    # 4. Index windows
    # ---------------------------------------------------------

    store.upsert_windows(
        windows=windows,
        embeddings=embeddings,
        video_id=VIDEO_ID,
    )

    print(
        "PASS: Audio windows indexed"
    )

    # ---------------------------------------------------------
    # 5. Search using first window embedding
    # ---------------------------------------------------------

    results = store.search(
        embeddings[0],
        limit=3,
    )

    print()
    print(
        "SEARCH RESULTS:"
    )

    for result in results:

        print(
            result
        )

        print(
            "PAYLOAD =",
            result.payload,
        )

    assert len(results) >= 1

    assert (
        results[0].payload["video_id"]
        == VIDEO_ID
    )

    assert (
        results[0].payload["start_ms"]
        == windows[0].start_ms
    )

    assert (
        results[0].payload["end_ms"]
        == windows[0].end_ms
    )

    print(
        "PASS: Correct audio window first"
    )

    print(
        "PASS: Payload metadata"
    )

    print()
    print("=" * 70)
    print("AUDIO QDRANT = PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()