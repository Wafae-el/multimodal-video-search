from packages.audio_quality.quality import audio_quality, renormalize_active_weights


def test_audio_quality_penalizes_bad_audio_without_erasing_channels():
    good = audio_quality(1.0, 1.0, 0.9, 0.0)
    noisy = audio_quality(0.1, 0.2, 0.4, 1.0)
    assert good > noisy
    assert audio_quality(0.0, 0.0, 0.0, 0.0) == 0.0
    assert renormalize_active_weights(
        {"text": 0.5, "audio": 0.25, "visual": 0.25}, {"text", "visual"}
    ) == {"text": 2 / 3, "audio": 0.0, "visual": 1 / 3}
