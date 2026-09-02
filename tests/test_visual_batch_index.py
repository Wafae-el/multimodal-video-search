from dataclasses import dataclass
from pathlib import Path

from packages.visual.openclip_encoder import OpenCLIPVisualEncoder
from packages.retrieval.visual_qdrant_store import VisualQdrantStore


@dataclass
class FrameMetadata:
    scene_id: int
    timestamp_ms: int
    object_key: str


def main():
    print("=" * 70)
    print("WEEK 4 - VISUAL BATCH INDEXING")
    print("=" * 70)

    # --------------------------------------------------
    # 1. Frame metadata
    # --------------------------------------------------

    frames = [
        FrameMetadata(
            scene_id=4,
            timestamp_ms=18718,
            object_key=(
                "media-derived/"
                "09ab06ce-2192-4a1e-992e-360d16cc432e/"
                "frames/scene_4.jpg"
            ),
        ),
    ]

    image_paths = [
        Path(__file__).parent / "fixtures" / "test_frame.jpg",
    ]

    print("FRAMES =", len(frames))

    assert len(frames) == len(image_paths)

    print("PASS: Frame metadata")

    # --------------------------------------------------
    # 2. OpenCLIP
    # --------------------------------------------------

    encoder = OpenCLIPVisualEncoder(
        model_name="ViT-B-32",
        pretrained="openai",
        device="cpu",
    )

    print("PASS: OpenCLIP loaded")
    print("DIMENSION =", encoder.dimension)

    assert encoder.dimension == 512

    # --------------------------------------------------
    # 3. Batch encoding
    # --------------------------------------------------

    embeddings = encoder.encode_images(
        image_paths
    )

    print("EMBEDDINGS =", len(embeddings))

    assert len(embeddings) == len(frames)
    assert embeddings.shape[1] == 512

    print("PASS: Batch encoding")
    print("PASS: One embedding per frame")
    print("PASS: Embedding dimension = 512")

    # --------------------------------------------------
    # 4. Qdrant
    # --------------------------------------------------

    store = VisualQdrantStore(
        url="http://qdrant:6333",
    )

    store.create_collection()

    print("PASS: Visual collection")

    # --------------------------------------------------
    # 5. Batch indexing
    # --------------------------------------------------

    store.upsert_frames(
        frames=frames,
        embeddings=embeddings,
        video_id=10,
    )

    print("PASS: Batch indexing")

    # --------------------------------------------------
    # 6. Search
    # --------------------------------------------------

    results = store.search(
        embeddings[0],
        limit=5,
    )

    print()
    print("SEARCH RESULTS:")

    for result in results:
        print(result)
        print("PAYLOAD =", result.payload)

    assert results

    # --------------------------------------------------
    # 7. Validate metadata
    # --------------------------------------------------

    top = results[0]

    assert top.payload["video_id"] == 10
    assert top.payload["scene_id"] == 4
    assert top.payload["timestamp_ms"] == 18718
    assert top.payload["object_key"] == frames[0].object_key
    assert top.payload["embedding_model"] == "ViT-B-32"
    assert top.payload["embedding_provider"] == "openai"
    assert top.payload["modality"] == "image"

    print()
    print("PASS: video_id")
    print("PASS: scene_id")
    print("PASS: timestamp_ms")
    print("PASS: object_key")
    print("PASS: embedding metadata")

    print()
    print("=" * 70)
    print("VISUAL BATCH INDEXING = PASS")
    print("=" * 70)


def test_visual_batch_index():
    main()


if __name__ == "__main__":
    main()