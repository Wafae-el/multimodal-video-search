from pathlib import Path
import cv2


def extract_representative_frames(
    video_path: Path,
    scenes: list,
    output_dir: Path,
    sample_interval_sec: int = 10,
):
    """
    Extract representative frames.

    - Short scenes: one frame at the middle.
    - Long scenes: one frame every sample_interval_sec seconds.
    """

    output_dir.mkdir(exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))

    fps = cap.get(cv2.CAP_PROP_FPS)

    extracted_frames = []

    for scene in scenes:

        start_ms = scene["start_ms"]
        end_ms = scene["end_ms"]

        duration_sec = (end_ms - start_ms) / 1000

        timestamps = []

        if duration_sec <= sample_interval_sec:

            timestamps.append((start_ms + end_ms) / 2)

        else:

            current = start_ms

            while current < end_ms:

                timestamps.append(current)

                current += sample_interval_sec * 1000

        for index, timestamp in enumerate(timestamps, start=1):

            frame_number = int((timestamp / 1000) * fps)

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

            success, frame = cap.read()

            if success:

                filename = (
                    output_dir
                    / f"scene_{scene['scene_id']:03d}_{index:03d}.jpg"
                )

                cv2.imwrite(str(filename), frame)

                extracted_frames.append(
                    {
                        "scene_id": scene["scene_id"],
                        "frame_path": str(filename),
                        "timestamp_ms": int(timestamp),
                    }
                )

    cap.release()

    return extracted_frames