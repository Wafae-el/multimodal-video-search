from pathlib import Path

from packages.speech.whisper_service import WhisperService


def test_whisper_service():
    audio_path = Path("tests/fixtures/source.wav")

    service = WhisperService(
        model_size="tiny",
        device="cpu",
        compute_type="int8",
    )

    segments = service.transcribe(audio_path)

    assert isinstance(segments, list)

    for segment in segments:
        assert segment.start_ms >= 0
        assert segment.end_ms > segment.start_ms
        assert segment.text