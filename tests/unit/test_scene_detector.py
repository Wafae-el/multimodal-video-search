from pathlib import Path

import pytest

from packages.media.scene_detector import SceneDetector, SceneSegment


def test_empty_video_returns_empty(monkeypatch):
    detector = SceneDetector()

    class FakeVideo:
        duration = type("Duration", (), {"get_seconds": lambda self: 0})()

    monkeypatch.setattr(
        "packages.media.scene_detector.open_video",
        lambda _: FakeVideo(),
    )

    class FakeManager:
        def add_detector(self, detector):
            pass

        def detect_scenes(self, video):
            pass

        def get_scene_list(self):
            return []

    monkeypatch.setattr(
        "packages.media.scene_detector.SceneManager",
        FakeManager,
    )

    scenes = detector.detect(Path("dummy.mp4"))

    assert len(scenes) == 1
    assert scenes[0].start_ms == 0
    assert scenes[0].end_ms == 0
    assert scenes[0].duration_ms == 0


def test_no_cut_returns_single_scene(monkeypatch):
    detector = SceneDetector()

    class FakeVideo:
        duration = type("Duration", (), {"get_seconds": lambda self: 45})()

    monkeypatch.setattr(
        "packages.media.scene_detector.open_video",
        lambda _: FakeVideo(),
    )

    class FakeManager:
        def add_detector(self, detector):
            pass

        def detect_scenes(self, video):
            pass

        def get_scene_list(self):
            return []

    monkeypatch.setattr(
        "packages.media.scene_detector.SceneManager",
        FakeManager,
    )

    scenes = detector.detect(Path("dummy.mp4"))

    assert len(scenes) == 1
    assert scenes[0].start_ms == 0
    assert scenes[0].end_ms == 45000


def test_scene_segment_duration():
    scene = SceneSegment(
        scene_id=0,
        start_ms=1000,
        end_ms=5500,
        duration_ms=4500,
    )

    assert scene.duration_ms == 4500