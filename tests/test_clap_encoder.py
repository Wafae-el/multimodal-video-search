from pathlib import Path

import numpy as np
import soundfile as sf

from packages.audio.clap_encoder import CLAPAudioEncoder


AUDIO_PATH = Path("tests/test_clap_audio.wav")


def main():

    print("=" * 70)
    print("WEEK 5 - CLAP AUDIO ENCODER")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. Create synthetic audio
    # ---------------------------------------------------------

    sample_rate = 48000
    duration = 5

    t = np.linspace(
        0,
        duration,
        sample_rate * duration,
        endpoint=False,
    )

    audio = (
        0.2 * np.sin(
            2 * np.pi * 440 * t
        )
    ).astype(np.float32)

    sf.write(
        AUDIO_PATH,
        audio,
        sample_rate,
    )

    print("PASS: Test audio created")

    # ---------------------------------------------------------
    # 2. Load CLAP
    # ---------------------------------------------------------

    encoder = CLAPAudioEncoder(
        device="cpu",
    )

    print(
        "PASS: CLAP loaded"
    )

    print(
        "CLAP DIMENSION =",
        encoder.dimension,
    )

    assert encoder.dimension == 512

    # ---------------------------------------------------------
    # 3. Audio embedding
    # ---------------------------------------------------------

    audio_embedding = (
        encoder.encode_audio(
            AUDIO_PATH
        )
    )

    print(
        "AUDIO EMBEDDING DIMENSION =",
        len(audio_embedding),
    )

    audio_norm = float(
        np.linalg.norm(
            audio_embedding
        )
    )

    print(
        "AUDIO NORM =",
        audio_norm,
    )

    assert len(audio_embedding) == 512
    assert np.isclose(
        audio_norm,
        1.0,
        atol=1e-4,
    )

    print(
        "PASS: Audio embedding"
    )

    # ---------------------------------------------------------
    # 4. Text embedding
    # ---------------------------------------------------------

    text_embedding = (
        encoder.encode_text(
            "a musical sound"
        )
    )

    print(
        "TEXT EMBEDDING DIMENSION =",
        len(text_embedding),
    )

    text_norm = float(
        np.linalg.norm(
            text_embedding
        )
    )

    print(
        "TEXT NORM =",
        text_norm,
    )

    assert len(text_embedding) == 512
    assert np.isclose(
        text_norm,
        1.0,
        atol=1e-4,
    )

    print(
        "PASS: Text embedding"
    )

    # ---------------------------------------------------------
    # 5. Audio ↔ Text similarity
    # ---------------------------------------------------------

    similarity = float(
        np.dot(
            audio_embedding,
            text_embedding,
        )
    )

    print(
        "AUDIO/TEXT SIMILARITY =",
        similarity,
    )

    assert -1.0 <= similarity <= 1.0

    print(
        "PASS: Audio/Text cosine similarity"
    )

    # ---------------------------------------------------------
    # 6. Batch encoding
    # ---------------------------------------------------------

    batch = (
        encoder.encode_audio_batch(
            [
                AUDIO_PATH,
                AUDIO_PATH,
            ]
        )
    )

    print(
        "BATCH SHAPE =",
        batch.shape,
    )

    assert batch.shape == (
        2,
        512,
    )

    print(
        "PASS: Batch audio encoding"
    )

    print()
    print("=" * 70)
    print("CLAP AUDIO ENCODER = PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()