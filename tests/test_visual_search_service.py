from pathlib import Path

from packages.retrieval.visual_search import VisualSearchService
from packages.storage.minio_service import client


OBJECT_KEY = (
    "media-derived/"
    "09ab06ce-2192-4a1e-992e-360d16cc432e/"
    "frames/scene_4.jpg"
)

LOCAL_FRAME = Path("/tmp/visual_search_scene_4.jpg")


def main():

    print("=" * 70)
    print("WEEK 4 - VISUAL SEARCH SERVICE")
    print("=" * 70)

    # ------------------------------------------------------------
    # 1. Download a real archive frame from MinIO
    # ------------------------------------------------------------

    client.fget_object(
        "media",
        OBJECT_KEY,
        str(LOCAL_FRAME),
    )

    print("PASS: Archive frame downloaded")

    # ------------------------------------------------------------
    # 2. Create the real visual search service
    # ------------------------------------------------------------

    service = VisualSearchService(
        qdrant_url="http://qdrant:6333",
        collection_name="video_visual_frames",
        model_name="ViT-B-32",
        pretrained="openai",
        device="cpu",
    )

    print("PASS: Visual search service loaded")

    # ------------------------------------------------------------
    # 3. Image -> Frame
    # ------------------------------------------------------------

    image_results = service.search_image(
        LOCAL_FRAME,
        limit=5,
    )

    print()
    print("IMAGE -> FRAME")
    print("RESULTS =", len(image_results))

    for result in image_results:
        print(result)
        print(
            "  video_id =",
            result.video_id,
        )
        print(
            "  scene_id =",
            result.scene_id,
        )
        print(
            "  timestamp_ms =",
            result.timestamp_ms,
        )
        print(
            "  score =",
            result.score,
        )
        print(
            "  object_key =",
            result.object_key,
        )

    assert len(image_results) >= 1

    best = image_results[0]

    assert best.video_id == 10
    assert best.scene_id == 4
    assert best.timestamp_ms == 18718
    assert best.object_key == OBJECT_KEY

    print("PASS: Image -> Frame")
    print("PASS: Correct scene first")
    print("PASS: Timestamp returned")
    print("PASS: Preview/object key returned")

    # ------------------------------------------------------------
    # 4. Text -> Frame
    # ------------------------------------------------------------

    text_results = service.search_text(
        "machine learning",
        limit=5,
    )

    print()
    print("TEXT -> FRAME")
    print("RESULTS =", len(text_results))

    for result in text_results:
        print(result)
        print(
            "  scene_id =",
            result.scene_id,
        )
        print(
            "  timestamp_ms =",
            result.timestamp_ms,
        )
        print(
            "  score =",
            result.score,
        )

    assert len(text_results) >= 1

    print("PASS: Text -> Frame")

    # ------------------------------------------------------------
    # 5. Multi-frame search
    # ------------------------------------------------------------

    multi_results = service.search_frames(
        [LOCAL_FRAME],
        per_query_limit=5,
        final_limit=5,
    )

    print()
    print("MULTI-FRAME SEARCH")
    print("RESULTS =", len(multi_results))

    for result in multi_results:
        print(result)

    assert len(multi_results) >= 1

    print("PASS: Multi-frame search")

    # ------------------------------------------------------------
    # 6. Scene / clip aggregation
    # ------------------------------------------------------------

    clip_results = (
        service.aggregate_results_by_scene(
            multi_results
        )
    )

    print()
    print("SCENE / CLIP AGGREGATION")
    print("RESULTS =", len(clip_results))

    for result in clip_results:
        print(
            "clip_id =",
            result.clip_id,
        )
        print(
            "video_id =",
            result.video_id,
        )
        print(
            "scene_id =",
            result.scene_id,
        )
        print(
            "score =",
            result.score,
        )
        print(
            "max_score =",
            result.max_score,
        )
        print(
            "top_r_mean =",
            result.top_r_mean,
        )
        print(
            "matched_frames =",
            result.matched_frames,
        )

    assert len(clip_results) >= 1

    best_clip = clip_results[0]

    assert best_clip.video_id == 10
    assert best_clip.scene_id == 4
    assert best_clip.max_score > 0
    assert best_clip.top_r_mean > 0
    assert best_clip.score > 0

    print("PASS: Scene aggregation")
    print("PASS: Max + top-r mean")
    print("PASS: Correct scene first")

    # ------------------------------------------------------------
    # Final
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("VISUAL SEARCH SERVICE = PASS")
    print("=" * 70)


def test_visual_search_service():
    main()


if __name__ == "__main__":
    main()