import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


FFPROBE_TIMEOUT = 30


class MediaValidationError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass
class VideoMetadata:
    duration: float
    size: int
    video_codec: str
    width: int
    height: int
    has_audio: bool


def analyze_video(video_path: Path) -> VideoMetadata:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT,
            check=True,
        )

    except FileNotFoundError:
        raise MediaValidationError("FFPROBE_UNAVAILABLE")

    except subprocess.TimeoutExpired:
        raise MediaValidationError("FFPROBE_TIMEOUT")

    except subprocess.CalledProcessError:
        raise MediaValidationError("CORRUPT_MEDIA")

    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise MediaValidationError("UNSUPPORTED_MEDIA")

    streams = metadata.get("streams", [])

    video_stream = next(
        (s for s in streams if s.get("codec_type") == "video"),
        None,
    )

    if video_stream is None:
        raise MediaValidationError("MISSING_VIDEO_STREAM")

    audio_stream = next(
        (s for s in streams if s.get("codec_type") == "audio"),
        None,
    )

    return VideoMetadata(
        duration=float(metadata["format"]["duration"]),
        size=int(metadata["format"]["size"]),
        video_codec=video_stream["codec_name"],
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        has_audio=audio_stream is not None,
    )