from pathlib import Path

from packages.storage.minio_service import client
from packages.visual.openclip_encoder import OpenCLIPVisualEncoder
from packages.retrieval.visual_qdrant_store import VisualQdrantStore


VIDEO_ID = 10
SCENE_ID = 4
TIMESTAMP_MS = 18718

OBJECT_KEY = (
    "media-derived/"
    "09ab06ce-2192-4a1e-992e-360d16cc432e/"
    "frames/scene_4.jpg"
)

LOCAL_FRAME = Path("/tmp/visual_scene_4.jpg")


def main():

    print("=" * 70)
    print("WEEK 4 - VISUAL FRAME INDEXING")
    print("=" * 70)

    # 1. Download frame from MinIO
    client.fget_object(
        "media",
        OBJECT_KEY,
        str(LOCAL_FRAME),
    )

    print("PASS: Frame downloaded")

    # 2. Load OpenCLIP
    encoder = OpenCLIPVisualEncoder(
        model_name="ViT-B-32",
        pretrained="openai",
        device="cpu",
    )

    print("PASS: OpenCLIP loaded")

    # 3. Encode frame
    embedding = encoder.encode_image(
        LOCAL_FRAME
    )

    print(
        "PASS: Visual embedding",
        "dimension =", len(embedding),
    )

    # 4. Create frame metadata
    class Frame:
        scene_id = SCENE_ID
        timestamp_ms = TIMESTAMP_MS
        object_key = OBJECT_KEY

    frame = Frame()

    # 5. Create Qdrant store
    store = VisualQdrantStore(
        url="http://qdrant:6333",
    )

    store.create_collection()

    # 6. Index embedding
    store.upsert_frames(
        frames=[frame],
        embeddings=[embedding],
        video_id=VIDEO_ID,
    )

    print("PASS: Frame indexed")

    # 7. Verify search
    results = store.search(
        embedding,
        limit=1,
    )

    print("SEARCH RESULTS:")

    for result in results:
        print(result)
        print("PAYLOAD =", result.payload)

    # 8. Final validation
    assert len(results) == 1
    assert results[0].payload["video_id"] == VIDEO_ID
    assert results[0].payload["scene_id"] == SCENE_ID
    assert results[0].payload["timestamp_ms"] == TIMESTAMP_MS
    assert results[0].payload["object_key"] == OBJECT_KEY

    print()
    print("=" * 70)
    print("VISUAL FRAME INDEXING = PASS")
    print("=" * 70)


def test_visual_index():
    main()


if __name__ == "__main__":
    main()