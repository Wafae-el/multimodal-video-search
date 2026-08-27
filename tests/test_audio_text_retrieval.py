from pathlib import Path

import numpy as np
import soundfile as sf

from packages.audio.clap_encoder import CLAPAudioEncoder
from packages.audio.windowing import AudioWindowGenerator
from packages.retrieval.audio_qdrant_store import AudioQdrantStore


VIDEO_ID = 20
AUDIO_DIR = Path("/tmp/clap_audio_windows")


def create_audio_files(windows):
    AUDIO_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    sample_rate = 48000

    paths = []

    for index, window in enumerate(windows):

        duration_ms = (
            window.end_ms
            - window.start_ms
        )

        samples = int(
            sample_rate
            * duration_ms
            / 1000
        )

        t = np.linspace(
            0,
            duration_ms / 1000,
            samples,
            endpoint=False,
        )

        # Different frequencies make the windows
        # different from one another.
        frequency = 220 + (
            index * 110
        )

        audio = (
            0.15
            * np.sin(
                2
                * np.pi
                * frequency
                * t
            )
        ).astype(np.float32)

        path = (
            AUDIO_DIR
            / f"window_{index}.wav"
        )

        sf.write(
            path,
            audio,
            sample_rate,
        )

        paths.append(path)

    return paths


def main():

    print("=" * 70)
    print("WEEK 5 - TEXT TO AUDIO RETRIEVAL")
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
    # 2. Create real audio files
    # ---------------------------------------------------------

    audio_paths = create_audio_files(
        windows
    )

    print(
        "AUDIO FILES =",
        len(audio_paths),
    )

    assert len(audio_paths) == 5

    print(
        "PASS: Audio files"
    )

    # ---------------------------------------------------------
    # 3. Load CLAP
    # ---------------------------------------------------------

    encoder = CLAPAudioEncoder(
        device="cpu",
    )

    print(
        "CLAP DIMENSION =",
        encoder.dimension,
    )

    assert encoder.dimension == 512

    print(
        "PASS: CLAP loaded"
    )

    # ---------------------------------------------------------
    # 4. Encode audio windows
    # ---------------------------------------------------------

    audio_embeddings = (
        encoder.encode_audio_batch(
            audio_paths
        )
    )

    print(
        "AUDIO EMBEDDINGS SHAPE =",
        audio_embeddings.shape,
    )

    assert audio_embeddings.shape == (
        5,
        512,
    )

    print(
        "PASS: Audio CLAP embeddings"
    )

    # ---------------------------------------------------------
    # 5. Create Qdrant store
    # ---------------------------------------------------------

    store = AudioQdrantStore(
        url="http://qdrant:6333",
    )

    store.create_collection()

    print(
        "PASS: Audio collection"
    )

    # ---------------------------------------------------------
    # 6. Index real CLAP embeddings
    # ---------------------------------------------------------

    store.upsert_windows(
        windows=windows,
        embeddings=audio_embeddings,
        video_id=VIDEO_ID,
    )

    print(
        "PASS: Real CLAP embeddings indexed"
    )

    # ---------------------------------------------------------
    # 7. Text query
    # ---------------------------------------------------------

    query = "music"

    text_embedding = (
        encoder.encode_text(
            query
        )
    )

    print(
        "TEXT QUERY =",
        query,
    )

    print(
        "TEXT EMBEDDING DIMENSION =",
        len(text_embedding),
    )

    assert len(text_embedding) == 512

    print(
        "PASS: Text CLAP embedding"
    )

    # ---------------------------------------------------------
    # 8. Text → Audio search
    # ---------------------------------------------------------

    results = store.search(
        text_embedding,
        limit=5,
    )

    print()
    print(
        "TEXT -> AUDIO RESULTS:"
    )

    for result in results:

        print(
            result
        )

        print(
            "  video_id =",
            result.payload.get(
                "video_id"
            ),
        )

        print(
            "  start_ms =",
            result.payload.get(
                "start_ms"
            ),
        )

        print(
            "  end_ms =",
            result.payload.get(
                "end_ms"
            ),
        )

        print(
            "  score =",
            result.score,
        )

        print(
            "  modality =",
            result.payload.get(
                "modality"
            ),
        )

    # ---------------------------------------------------------
    # 9. Validate results
    # ---------------------------------------------------------

    assert len(results) > 0

    first = results[0]

    assert (
        first.payload["video_id"]
        == VIDEO_ID
    )

    assert (
        first.payload["modality"]
        == "audio"
    )

    assert (
        "start_ms"
        in first.payload
    )

    assert (
        "end_ms"
        in first.payload
    )

    assert (
        -1.0
        <= first.score
        <= 1.0
    )

    print(
        "PASS: Text -> Audio retrieval"
    )

    print(
        "PASS: Audio timestamp returned"
    )

    print(
        "PASS: Audio payload returned"
    )

    print()
    print("=" * 70)
    print("TEXT TO AUDIO RETRIEVAL = PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()