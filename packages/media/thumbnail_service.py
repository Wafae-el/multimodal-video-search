from pathlib import Path
import subprocess

FFMPEG_TIMEOUT = 120


class ThumbnailGenerationError(Exception):
    pass


def generate_thumbnail(
    video_path: Path,
    thumbnail_path: Path,
    timestamp: str = "00:00:01",
) -> Path:
    thumbnail_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-ss",
        timestamp,
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(thumbnail_path),
    ]

    try:
        subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=FFMPEG_TIMEOUT,
            check=True,
        )

    except subprocess.TimeoutExpired:
        raise ThumbnailGenerationError(
            "THUMBNAIL_TIMEOUT"
        )

    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()[-500:]
        raise ThumbnailGenerationError(
            f"THUMBNAIL_GENERATION_FAILED: {stderr}"
        )

    if not thumbnail_path.exists():
        raise ThumbnailGenerationError(
            "THUMBNAIL_NOT_CREATED"
        )

    if thumbnail_path.stat().st_size == 0:
        raise ThumbnailGenerationError(
            "THUMBNAIL_EMPTY"
        )

    return thumbnail_path
