from packages.speech.whisper_service import TranscriptSegment
from packages.speech.normalizer import TranscriptNormalizer
from packages.speech.chunker import TranscriptChunker
from packages.retrieval.service import HybridRetrievalService


segments = [
    TranscriptSegment(
        0,
        4000,
        "The multimodal video search system uses Qdrant "
        "for semantic vector storage.",
        -0.10,
    ),
    TranscriptSegment(
        4000,
        8000,
        "The ASR pipeline uses Faster Whisper to convert "
        "spoken audio into searchable transcript text.",
        -0.11,
    ),
    TranscriptSegment(
        8000,
        12000,
        "The YOLOv8 model performs object detection "
        "on selected video frames.",
        -0.08,
    ),
    TranscriptSegment(
        12000,
        16000,
        "The BM25 algorithm provides exact lexical retrieval "
        "for names, acronyms and technical terms.",
        -0.09,
    ),
    TranscriptSegment(
        16000,
        20000,
        'The presenter says "search by meaning, not only keywords".',
        -0.10,
    ),
    TranscriptSegment(
        20000,
        24000,
        "The system was evaluated during the 2026 research phase.",
        -0.12,
    ),
    TranscriptSegment(
        24000,
        28000,
        "Dense retrieval finds passages with similar meaning "
        "even when the exact words are different.",
        -0.10,
    ),
    TranscriptSegment(
        28000,
        32000,
        "Sparse lexical search is especially useful for "
        "proper names, acronyms, numbers and quotations.",
        -0.09,
    ),
    TranscriptSegment(
        32000,
        36000,
        "La recherche vidéo multimodale combine la recherche "
        "sémantique et la recherche lexicale.",
        -0.11,
    ),
    TranscriptSegment(
        36000,
        40000,
        "البحث الدلالي يساعد على العثور على نصوص متشابهة "
        "في المعنى حتى عندما تختلف الكلمات.",
        -0.13,
    ),
]


normalizer = TranscriptNormalizer()
chunker = TranscriptChunker()

normalized = normalizer.normalize(segments)
chunks = chunker.chunk(normalized)

print("=" * 80)
print("WEEK 3 - SEARCH DUEL")
print("=" * 80)
print("CHUNKS =", len(chunks))

for chunk in chunks:
    print(
        f"{chunk.chunk_id}: "
        f"{chunk.start_ms}-{chunk.end_ms} ms"
    )


service = HybridRetrievalService()

service.index(
    chunks,
    video_id=999,
    language="multilingual",
)


queries = [
    ("EXACT NAME", "YOLOv8"),
    ("ACRONYM / TECHNICAL", "BM25"),
    ("NUMBER", "2026"),
    ("QUOTATION", "search by meaning"),
    (
        "PARAPHRASE",
        "How can the system find text with the same meaning "
        "when the words are different?",
    ),
    (
        "FRENCH",
        "recherche vidéo multimodale",
    ),
    (
        "ARABIC",
        "البحث الدلالي",
    ),
]


for title, query in queries:

    print()
    print("=" * 80)
    print(title)
    print("QUERY:", query)
    print("=" * 80)

    result = service.search(
        query,
        limit=3,
    )

    print()
    print("--- DENSE WIZARD ---")

    for item in result["dense"]:
        print(
            f"rank={item.rank} "
            f"score={item.score:.4f} "
            f"id={item.chunk_id}"
        )
        print(
            "  ",
            item.payload["text"][:180]
        )

    print()
    print("--- SPARSE ARCHER / BM25 ---")

    for item in result["sparse"]:
        print(
            f"rank={item.rank} "
            f"score={item.score:.4f} "
            f"id={item.chunk_id}"
        )

    print()
    print("--- FUSION / RRF ---")

    for item in result["fused"]:
        print(
            f"id={item.chunk_id} "
            f"rrf={item.score:.6f} "
            f"dense_rank={item.dense_rank} "
            f"sparse_rank={item.sparse_rank}"
        )