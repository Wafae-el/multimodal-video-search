from dataclasses import dataclass


@dataclass(frozen=True)
class RepresentativeFrame:
    scene_id: int
    scene_index: int
    timestamp_ms: int


class FrameSelector:
    def select(self, scenes):
        frames = []

        for scene in scenes:
            middle = (scene.start_ms + scene.end_ms) // 2

            frames.append(
                RepresentativeFrame(
                    scene_id=(
                        scene.id
                        if hasattr(scene, "id")
                        else scene.scene_id
                    ),
                    scene_index=(
                        scene.scene_index
                        if hasattr(scene, "scene_index")
                        else scene.scene_id
                    ),
                    timestamp_ms=middle,
                )
            )

        return frames