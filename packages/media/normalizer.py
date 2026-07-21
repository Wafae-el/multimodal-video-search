from pathlib import Path
import subprocess

FFMPEG_TIMEOUT = 300


class VideoNormalizationError(Exception):
    pass


def normalize_video(
    input_path: Path,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_path),
    ]

    try:
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=FFMPEG_TIMEOUT,
            check=True,
        )
    except subprocess.TimeoutExpired:
        raise VideoNormalizationError(
            "VIDEO_NORMALIZATION_TIMEOUT"
        )

    except subprocess.CalledProcessError:
        raise VideoNormalizationError(
            "VIDEO_NORMALIZATION_FAILED"
        )

    if not output_path.exists():
        raise VideoNormalizationError(
            "NORMALIZED_VIDEO_NOT_CREATED"
        )

    return output_path