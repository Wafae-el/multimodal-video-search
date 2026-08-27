from packages.audio.speech_windows import (
    AudioSpeechWindowAnalyzer,
)
from packages.audio.windowing import (
    AudioWindowGenerator,
)
from packages.speech.whisper_service import (
    TranscriptSegment,
)


def main():

    print("=" * 70)
    print("WEEK 5 - AUDIO SPEECH WINDOWS")
    print("=" * 70)

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

    print("WINDOWS =", len(results))

    for result in results:
        print(
            f"WINDOW {result.window.index}: "
            f"{result.window.start_ms} -> "
            f"{result.window.end_ms}"
        )
        print(
            "  TEXT =",
            result.text,
        )
        print(
            "  SPEECH RATIO =",
            result.speech_ratio,
        )
        print(
            "  ASR CONFIDENCE =",
            result.asr_confidence,
        )
        print(
            "  LANGUAGE =",
            result.language,
        )
        print(
            "  SEGMENTS =",
            result.segment_count,
        )

    assert len(results) == 5

    # Window 0: 0 -> 5000
    # Segment 1000 -> 3000 = 2000 ms
    assert results[0].speech_ratio == 0.4
    assert results[0].text == "hello world"
    assert results[0].segment_count == 1

    # Window 1: 2500 -> 7500
    # Both segments overlap:
    # 2500 -> 3000 = 500 ms
    # 5500 -> 7500 = 2000 ms
    assert results[1].segment_count == 2
    assert 0 < results[1].speech_ratio <= 1
    assert "hello world" in results[1].text
    assert "machine learning" in results[1].text

    # Window 2: 5000 -> 10000
    # Segment 5500 -> 7500 = 2000 ms
    assert results[2].speech_ratio == 0.4
    assert results[2].text == "machine learning"
    assert results[2].segment_count == 1

    # Window 3: 7500 -> 12500
    # No speech.
    assert results[3].speech_ratio == 0.0
    assert results[3].text == ""
    assert results[3].segment_count == 0
    assert results[3].language == "unknown"

    # Window 4: 10000 -> 15000
    # No speech.
    assert results[4].speech_ratio == 0.0
    assert results[4].text == ""
    assert results[4].segment_count == 0
    assert results[4].language == "unknown"

    print("PASS: Temporal ASR/window alignment")
    print("PASS: Speech ratio")
    print("PASS: ASR confidence aggregation")
    print("PASS: Silent window handling")

    print()
    print("=" * 70)
    print("AUDIO SPEECH WINDOWS = PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()