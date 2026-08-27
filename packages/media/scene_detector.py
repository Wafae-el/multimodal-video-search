from dataclasses import dataclass
from pathlib import Path

from scenedetect import SceneManager
from scenedetect import open_video
from scenedetect.detectors import ContentDetector


@dataclass
class SceneSegment:
    scene_id: int
    start_ms: int
    end_ms: int
    duration_ms: int


class SceneDetector:
    def __init__(self, threshold: float = 27.0):
        self.threshold = threshold

    def detect(self, video_path: Path) -> list[SceneSegment]:
        video = open_video(str(video_path))

        manager = SceneManager()
        manager.add_detector(
            ContentDetector(threshold=self.threshold)
        )

        manager.detect_scenes(video)

        scene_list = manager.get_scene_list()

        if not scene_list:
            duration_ms = int(video.duration.get_seconds() * 1000)
            return [
                SceneSegment(
                    scene_id=0,
                    start_ms=0,
                    end_ms=duration_ms,
                    duration_ms=duration_ms,
                )
            ]

        segments = []

        for index, (start, end) in enumerate(scene_list):

            start_ms = int(start.get_seconds() * 1000)
            end_ms = int(end.get_seconds() * 1000)

            segments.append(
                SceneSegment(
                    scene_id=index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    duration_ms=end_ms - start_ms,
                )
            )

        return segments
