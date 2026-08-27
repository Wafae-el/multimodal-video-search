from dataclasses import dataclass
import re
import unicodedata

from packages.speech.whisper_service import TranscriptSegment


@dataclass(frozen=True)
class NormalizedSegment:
    start_ms: int
    end_ms: int
    raw_text: str
    normalized_text: str
    confidence: float
    language: str


class TranscriptNormalizer:
    """
    Normalizes ASR text while preserving the original raw transcript.
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""

        # Unicode normalization
        text = unicodedata.normalize("NFKC", text)

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Normalize surrounding spaces
        text = text.strip()

        # Lowercase for lexical retrieval
        text = text.lower()

        return text

    def normalize(
        self,
        segments: list[TranscriptSegment],
    ) -> list[NormalizedSegment]:

        results = []

        for segment in segments:
            raw_text = segment.text.strip()

            if not raw_text:
                continue

            normalized_text = self.normalize_text(raw_text)

            if not normalized_text:
                continue

            results.append(
                NormalizedSegment(
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    confidence=segment.confidence,
                    language=segment.language,
                )
            )

        return results