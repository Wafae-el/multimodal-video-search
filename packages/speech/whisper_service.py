import numpy as np
from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    confidence: float
    language: str


class WhisperService:
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> list[TranscriptSegment]:

        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        segments, info = self.model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
        )

        detected_language = info.language or "unknown"

        results = []

        for segment in segments:
            text = segment.text.strip()

            if not text:
                continue

            results.append(
                TranscriptSegment(
                    start_ms=int(segment.start * 1000),
                    end_ms=int(segment.end * 1000),
                    text=text,
                    confidence=float(
                        max(
                            0.0,
                            min(
                                1.0,
                                np.exp(segment.avg_logprob),
                            ),
                        )
                    ),
                    language=detected_language,
                )
            )

        return results