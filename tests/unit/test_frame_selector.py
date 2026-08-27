from packages.media.frame_selector import (
    FrameSelector,
    RepresentativeFrame,
)
from packages.media.scene_detector import SceneSegment


def test_empty_scene_list():
    selector = FrameSelector()

    assert selector.select([]) == []


def test_single_scene():
    selector = FrameSelector()

    scenes = [
        SceneSegment(
            scene_id=0,
            start_ms=0,
            end_ms=10000,
            duration_ms=10000,
        )
    ]

    assert selector.select(scenes) == [
        RepresentativeFrame(
            scene_id=0,
            timestamp_ms=5000,
        )
    ]


def test_multiple_scenes():
    selector = FrameSelector()

    scenes = [
        SceneSegment(
            scene_id=0,
            start_ms=0,
            end_ms=4000,
            duration_ms=4000,
        ),
        SceneSegment(
            scene_id=1,
            start_ms=4000,
            end_ms=12000,
            duration_ms=8000,
        ),
    ]

    assert selector.select(scenes) == [
        RepresentativeFrame(
            scene_id=0,
            timestamp_ms=2000,
        ),
        RepresentativeFrame(
            scene_id=1,
            timestamp_ms=8000,
        ),
    ]