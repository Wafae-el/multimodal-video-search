from dataclasses import dataclass


@dataclass(frozen=True)
class RepresentativeFrame:
    scene_id: int
    timestamp_ms: int
    scene_index: int | None = None


class FrameSelector:
    def select(self, scenes):
        frames = []

        for scene in scenes:
            middle = (scene.start_ms + scene.end_ms) // 2

            scene_id = (
                scene.id
                if hasattr(scene, "id")
                else scene.scene_id
            )

            scene_index = (
                scene.scene_index
                if hasattr(scene, "scene_index")
                else None
            )

            frames.append(
                RepresentativeFrame(
                    scene_id=scene_id,
                    timestamp_ms=middle,
                    scene_index=scene_index,
                )
            )

        return frames