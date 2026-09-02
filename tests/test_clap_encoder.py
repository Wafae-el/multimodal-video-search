from pathlib import Path

import numpy as np
import soundfile as sf

from packages.audio.clap_encoder import CLAPAudioEncoder


AUDIO_PATH = Path("tests/test_clap_audio.wav")


def test_clap_encoder():
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
        0.2
        * np.sin(
            2 * np.pi * 440 * t
        )
    ).astype(np.float32)

    sf.write(
        AUDIO_PATH,
        audio,
        sample_rate,
    )

    # ---------------------------------------------------------
    # 2. Load CLAP
    # ---------------------------------------------------------

    encoder = CLAPAudioEncoder(
        device="cpu",
    )

    assert encoder.dimension == 512

    # ---------------------------------------------------------
    # 3. Audio embedding
    # ---------------------------------------------------------

    audio_embedding = encoder.encode_audio(
        AUDIO_PATH
    )

    audio_norm = float(
        np.linalg.norm(
            audio_embedding
        )
    )

    assert len(audio_embedding) == 512
    assert np.isclose(
        audio_norm,
        1.0,
        atol=1e-4,
    )

    # ---------------------------------------------------------
    # 4. Text embedding
    # ---------------------------------------------------------

    text_embedding = encoder.encode_text(
        "a musical sound"
    )

    text_norm = float(
        np.linalg.norm(
            text_embedding
        )
    )

    assert len(text_embedding) == 512
    assert np.isclose(
        text_norm,
        1.0,
        atol=1e-4,
    )

    # ---------------------------------------------------------
    # 5. Audio -> Text similarity
    # ---------------------------------------------------------

    similarity = float(
        np.dot(
            audio_embedding,
            text_embedding,
        )
    )

    assert -1.0 <= similarity <= 1.0

    # ---------------------------------------------------------
    # 6. Batch encoding
    # ---------------------------------------------------------

    batch = encoder.encode_audio_batch(
        [
            AUDIO_PATH,
            AUDIO_PATH,
        ]
    )

    assert batch.shape == (
        2,
        512,
    )