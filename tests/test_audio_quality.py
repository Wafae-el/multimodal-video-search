import numpy as np

from packages.audio.quality import AudioQualityAnalyzer


def test_audio_quality():
    analyzer = AudioQualityAnalyzer()

    sample_rate = 16000
    duration = 5
    samples = sample_rate * duration

    # CLEAN AUDIO
    t = np.linspace(
        0,
        duration,
        samples,
        endpoint=False,
    )

    clean = (
        0.3
        * np.sin(
            2 * np.pi * 440 * t
        )
    ).astype(np.float32)

    clean_quality = analyzer.analyze(
        clean,
        asr_confidence=0.9,
    )

    assert 0 <= clean_quality.speech_ratio <= 1
    assert 0 <= clean_quality.clipping_ratio <= 1
    assert 0 <= clean_quality.loudness <= 1
    assert 0 <= clean_quality.snr_norm <= 1
    assert 0 <= clean_quality.quality <= 1

    # SILENCE
    silence = np.zeros(
        samples,
        dtype=np.float32,
    )

    silence_quality = analyzer.analyze(
        silence,
        asr_confidence=0.0,
    )

    assert silence_quality.speech_ratio == 0.0
    assert silence_quality.clipping_ratio == 0.0
    assert 0 <= silence_quality.quality <= 1

    # CLIPPED AUDIO
    clipped = np.ones(
        samples,
        dtype=np.float32,
    )

    clipped_quality = analyzer.analyze(
        clipped,
        asr_confidence=0.5,
    )

    assert clipped_quality.clipping_ratio > 0.9
    assert 0 <= clipped_quality.quality <= 1

    # NOISY AUDIO
    rng = np.random.default_rng(42)

    noisy = (
        clean
        + 0.08
        * rng.normal(
            size=samples
        ).astype(np.float32)
    )

    noisy = np.clip(
        noisy,
        -1.0,
        1.0,
    )

    noisy_quality = analyzer.analyze(
        noisy,
        asr_confidence=0.7,
    )

    assert 0 <= noisy_quality.quality <= 1