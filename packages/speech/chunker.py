from dataclasses import dataclass

from packages.speech.normalizer import NormalizedSegment


@dataclass(frozen=True)
class TranscriptChunk:
    chunk_id: str
    start_ms: int
    end_ms: int
    text: str
    normalized_text: str
    source_segment_ids: list[int]
    confidence: float
    language: str


class TranscriptChunker:
    """
    Creates transcript chunks around 15-30 seconds.

    Chunks are built on Whisper segment boundaries instead of
    cutting blindly inside an ASR segment.
    """

    def __init__(
        self,
        target_ms: int = 20_000,
        max_ms: int = 30_000,
        overlap_ms: int = 2_000,
    ):
        self.target_ms = target_ms
        self.max_ms = max_ms
        self.overlap_ms = overlap_ms

    def chunk(
        self,
        segments: list[NormalizedSegment],
    ) -> list[TranscriptChunk]:

        if not segments:
            return []

        chunks = []
        current = []
        chunk_start_ms = None

        for segment_id, segment in enumerate(segments):

            if not current:
                chunk_start_ms = segment.start_ms

            proposed_duration = (
                segment.end_ms - chunk_start_ms
            )

            # If adding this segment would exceed the maximum,
            # close the current chunk first.
            if current and proposed_duration > self.max_ms:
                chunks.append(
                    self._build_chunk(
                        len(chunks),
                        current,
                    )
                )

                # Keep only segments that genuinely overlap
                # the previous chunk.
                overlap_start = (
                    current[-1][1].end_ms
                    - self.overlap_ms
                )

                overlap = [
                    item
                    for item in current
                    if item[1].end_ms > overlap_start
                ]

                current = overlap

                if current:
                    chunk_start_ms = current[0][1].start_ms
                else:
                    chunk_start_ms = segment.start_ms

            current.append((segment_id, segment))

            duration = (
                current[-1][1].end_ms
                - chunk_start_ms
            )

            # Close only if we have reached the target
            # and there is no reason to wait for another segment.
            if duration >= self.target_ms:

                # If this is already the final segment,
                # don't create a duplicate overlap-only chunk.
                if segment_id == len(segments) - 1:
                    chunks.append(
                        self._build_chunk(
                            len(chunks),
                            current,
                        )
                    )
                    current = []
                    break

                chunks.append(
                    self._build_chunk(
                        len(chunks),
                        current,
                    )
                )

                overlap_start = (
                    current[-1][1].end_ms
                    - self.overlap_ms
                )

                overlap = [
                    item
                    for item in current
                    if item[1].end_ms > overlap_start
                ]

                current = overlap

                if current:
                    chunk_start_ms = current[0][1].start_ms
                else:
                    chunk_start_ms = None

        # Add remaining content only if it is not already represented.
        if current:
            new_start = current[0][1].start_ms

            if not chunks or new_start > chunks[-1].start_ms:
                chunks.append(
                    self._build_chunk(
                        len(chunks),
                        current,
                    )
                )

        return chunks

    @staticmethod
    def _build_chunk(
        chunk_index: int,
        segments: list[tuple[int, NormalizedSegment]],
    ) -> TranscriptChunk:

        first = segments[0][1]
        last = segments[-1][1]

        raw_text = " ".join(
            segment.raw_text
            for _, segment in segments
        )

        normalized_text = " ".join(
            segment.normalized_text
            for _, segment in segments
        )

        confidences = [
            segment.confidence
            for _, segment in segments
        ]

        confidence = (
            sum(confidences) / len(confidences)
            if confidences
            else 0.0
        )

        return TranscriptChunk(
            chunk_id=f"speech-{chunk_index:06d}",
            start_ms=first.start_ms,
            end_ms=last.end_ms,
            text=raw_text,
            normalized_text=normalized_text,
            source_segment_ids=[
                segment_id
                for segment_id, _ in segments
            ],
            confidence=confidence,
            language=first.language,
        )