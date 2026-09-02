from packages.audio.windowing import AudioWindowGenerator


def test_audio_windowing():
    generator = AudioWindowGenerator(
        window_ms=5000,
        overlap_ms=2500,
    )

    windows = generator.generate(
        duration_ms=15000
    )

    assert len(windows) == 5

    assert windows[0].start_ms == 0
    assert windows[0].end_ms == 5000

    assert windows[1].start_ms == 2500
    assert windows[1].end_ms == 7500

    assert windows[2].start_ms == 5000
    assert windows[2].end_ms == 10000

    assert windows[3].start_ms == 7500
    assert windows[3].end_ms == 12500

    assert windows[4].start_ms == 10000
    assert windows[4].end_ms == 15000