from packages.audio.speech_windows import AudioSpeechWindowAnalyzer
from packages.audio.windowing import AudioWindowGenerator
from packages.speech.whisper_service import TranscriptSegment


def test_audio_speech_windows():
    generator = AudioWindowGenerator(
        window_ms=5000,
        overlap_ms=2500,
    )

    windows = generator.generate(
        duration_ms=15000
    )

    segments = [
        TranscriptSegment(
            start_ms=1000,
            end_ms=3000,
            text="hello world",
            confidence=-0.10,
            language="en",
        ),
        TranscriptSegment(
            start_ms=5500,
            end_ms=7500,
            text="machine learning",
            confidence=-0.20,
            language="en",
        ),
    ]

    analyzer = AudioSpeechWindowAnalyzer()

    results = analyzer.analyze(
        windows,
        segments,
    )

    assert len(results) == 5

    # Window 0: 0 -> 5000
    assert results[0].speech_ratio == 0.4
    assert results[0].text == "hello world"
    assert results[0].segment_count == 1

    # Window 1: 2500 -> 7500
    assert results[1].segment_count == 2
    assert 0 < results[1].speech_ratio <= 1
    assert "hello world" in results[1].text
    assert "machine learning" in results[1].text

    # Window 2: 5000 -> 10000
    assert results[2].speech_ratio == 0.4
    assert results[2].text == "machine learning"
    assert results[2].segment_count == 1

    # Window 3: 7500 -> 12500
    assert results[3].speech_ratio == 0.0
    assert results[3].text == ""
    assert results[3].segment_count == 0
    assert results[3].language == "unknown"

    # Window 4: 10000 -> 15000
    assert results[4].speech_ratio == 0.0
    assert results[4].text == ""
    assert results[4].segment_count == 0
    assert results[4].language == "unknown"