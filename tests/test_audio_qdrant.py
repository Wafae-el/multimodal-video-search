import numpy as np
import pytest

from packages.audio.windowing import AudioWindowGenerator
from packages.retrieval.audio_qdrant_store import AudioQdrantStore


VIDEO_ID = 10
QDRANT_URL = "http://qdrant:6333"


@pytest.mark.integration
def test_audio_qdrant():
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

    assert len(windows) == 5

    # ---------------------------------------------------------
    # 2. Create deterministic test embeddings
    # ---------------------------------------------------------

    embeddings = []

    for index in range(len(windows)):
        vector = np.zeros(
            512,
            dtype=np.float32,
        )

        vector[index] = 1.0

        embeddings.append(vector)

    assert len(embeddings) == 5
    assert embeddings[0].shape[0] == 512

    # ---------------------------------------------------------
    # 3. Create Qdrant collection
    # ---------------------------------------------------------

    store = AudioQdrantStore(
        url=QDRANT_URL,
    )

    store.create_collection()

    # ---------------------------------------------------------
    # 4. Index windows
    # ---------------------------------------------------------

    store.upsert_windows(
        windows=windows,
        embeddings=embeddings,
        video_id=VIDEO_ID,
    )

    # ---------------------------------------------------------
    # 5. Search using first window embedding
    # ---------------------------------------------------------

    results = store.search(
        embeddings[0],
        limit=3,
    )

    assert len(results) >= 1

    assert results[0].payload["video_id"] == VIDEO_ID

    assert (
        results[0].payload["start_ms"]
        == windows[0].start_ms
    )

    assert (
        results[0].payload["end_ms"]
        == windows[0].end_ms
    )