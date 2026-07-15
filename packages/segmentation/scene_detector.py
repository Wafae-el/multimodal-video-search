from pathlib import Path

from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector


def detect_scenes(video_path: Path):
    """
    Detect scenes in a video and return a list of dictionaries.

    Returns:
        [
            {
                "scene_id": 1,
                "start_ms": 0,
                "end_ms": 12500,
            },
            ...
        ]
    """

    video = open_video(str(video_path))

    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())

    scene_manager.detect_scenes(video)

    scene_list = scene_manager.get_scene_list()

    scenes = []

    for index, (start, end) in enumerate(scene_list, start=1):

        scenes.append(
            {
                "scene_id": index,
                "start_ms": int(start.get_seconds() * 1000),
                "end_ms": int(end.get_seconds() * 1000),
            }
        )

    return scenes