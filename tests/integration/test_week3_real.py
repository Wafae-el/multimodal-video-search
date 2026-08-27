from pathlib import Path

from packages.speech.whisper_service import WhisperService
from packages.speech.normalizer import TranscriptNormalizer
from packages.speech.chunker import TranscriptChunker
from packages.retrieval.service import HybridRetrievalService


AUDIO = Path("/tmp/test_source.wav")


def check(condition, message):
    if not condition:
        raise AssertionError(f"FAIL: {message}")
    print(f"PASS: {message}")


def main():
    print("=" * 70)
    print("WEEK 3 - FINAL VALIDATION")
    print("=" * 70)

    # ================================================================
    # 1. ASR
    # ================================================================

    whisper = WhisperService(
        model_size="small",
        device="cpu",
        compute_type="int8",
    )

    segments = whisper.transcribe(AUDIO)

    check(len(segments) > 0, "ASR transcription")

    print("SEGMENTS =", len(segments))

    # ================================================================
    # 2. NORMALIZATION
    # ================================================================

    normalized = TranscriptNormalizer().normalize(segments)

    check(
        len(normalized) == len(segments),
        "Normalization preserves segments",
    )

    check(
        all(segment.raw_text for segment in normalized),
        "Raw transcript preserved",
    )

    check(
        all(segment.normalized_text for segment in normalized),
        "Normalized transcript available",
    )

    check(
        all(segment.language for segment in normalized),
        "Language preserved",
    )

    check(
        all(hasattr(segment, "confidence") for segment in normalized),
        "Confidence preserved",
    )

    # ================================================================
    # 3. CHUNKING
    # ================================================================

    chunks = TranscriptChunker().chunk(normalized)

    check(len(chunks) > 0, "Transcript chunking")

    print("CHUNKS   =", len(chunks))

    check(
        all(chunk.start_ms < chunk.end_ms for chunk in chunks),
        "Valid chunk timestamps",
    )

    check(
        all(chunk.source_segment_ids for chunk in chunks),
        "Source ASR segment IDs preserved",
    )

    check(
        all(chunk.text for chunk in chunks),
        "Chunk raw text preserved",
    )

    check(
        all(chunk.normalized_text for chunk in chunks),
        "Chunk normalized text preserved",
    )

    check(
        all(chunk.language for chunk in chunks),
        "Chunk language preserved",
    )

    check(
        all(hasattr(chunk, "confidence") for chunk in chunks),
        "Chunk confidence preserved",
    )

    # ================================================================
    # 4. HYBRID RETRIEVAL
    # ================================================================

    retrieval = HybridRetrievalService(
        qdrant_url="http://qdrant:6333",
    )

    retrieval.index(
        chunks=chunks,
        video_id=10,
        language=chunks[0].language,
    )

    print("INDEXING = OK")

    # ================================================================
    # 5. SEARCH DUEL
    # ================================================================

    queries = [
        ("cross-validation", "cross-validation"),
        ("machine learning", "machine learning"),
        ("heart disease", "heart disease"),
    ]

    for query, expected_text in queries:

        print()
        print("=" * 70)
        print("QUERY:", query)
        print("=" * 70)

        result = retrieval.search(
            query,
            limit=3,
        )

        dense = result["dense"]
        sparse = result["sparse"]
        fused = result["fused"]

        # Dense
        check(
            len(dense) == 3,
            f"Dense Top-3 available for '{query}'",
        )

        print()
        print("--- DENSE ---")
        for item in dense:
            print(item)

        # BM25
        check(
            len(sparse) == 3,
            f"BM25 Top-3 available for '{query}'",
        )

        print()
        print("--- BM25 ---")
        for item in sparse:
            print(item)

        # RRF
        check(
            len(fused) > 0,
            f"RRF results available for '{query}'",
        )

        print()
        print("--- RRF ---")
        for item in fused:
            print(item)

        # ============================================================
        # Verify evidence through Qdrant
        # ============================================================

        dense_payload = dense[0].payload

        check(
            "text" in dense_payload,
            f"Text evidence available for '{query}'",
        )

        check(
            "normalized_text" in dense_payload,
            f"Normalized text evidence available for '{query}'",
        )

        check(
            "language" in dense_payload,
            f"Language evidence available for '{query}'",
        )

        check(
            "confidence" in dense_payload,
            f"Confidence evidence available for '{query}'",
        )

        check(
            "source_segment_ids" in dense_payload,
            f"Source ASR IDs available for '{query}'",
        )

        # ============================================================
        # Exact lexical match / relevance check
        # ============================================================

        top_texts = []

        for item in dense:
            text = item.payload.get("normalized_text", "")
            top_texts.append(text)

        for item in sparse:
            top_texts.append(
                next(
                    (
                        chunk.normalized_text
                        for chunk in chunks
                        if chunk.chunk_id == item.chunk_id
                    ),
                    "",
                )
            )

        relevance_found = any(
            expected_text.lower() in text.lower()
            for text in top_texts
        )

        check(
            relevance_found,
            f"Relevant result found for '{query}'",
        )

    # ================================================================
    # 6. FINAL SUMMARY
    # ================================================================

    print()
    print("=" * 70)
    print("WEEK 3 FINAL VALIDATION = PASS")
    print("=" * 70)

    print()
    print("ASR                    : PASS")
    print("NORMALIZATION          : PASS")
    print("CHUNKING               : PASS")
    print("SOURCE ASR IDS         : PASS")
    print("LANGUAGE               : PASS")
    print("CONFIDENCE             : PASS")
    print("DENSE RETRIEVAL        : PASS")
    print("BM25 RETRIEVAL         : PASS")
    print("RRF FUSION             : PASS")
    print("QDRANT EVIDENCE        : PASS")
    print("REAL VIDEO SEARCH      : PASS")
    print()
    print("WEEK 3 = COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()