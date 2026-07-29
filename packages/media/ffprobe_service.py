import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


FFPROBE_TIMEOUT = 30


class MediaValidationError(Exception):
    """Raised for problems with the *input* media (corrupt/unsupported). These
    are treated as non-retryable by the pipeline."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class OutputValidationError(Exception):
    """Raised when a freshly produced *output* artifact fails verification. These
    are treated as retryable (a bad FFmpeg run may succeed on retry)."""

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


@dataclass
class AudioMetadata:
    codec: str
    sample_rate: int
    channels: int
    duration: float


def _run_ffprobe(video_path: Path) -> dict:
    """Run ffprobe and return parsed JSON, with stable input-media errors."""
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
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise MediaValidationError("UNSUPPORTED_MEDIA")


def analyze_video(video_path: Path) -> VideoMetadata:
    """Validate input media: valid JSON, a video stream, typed metadata."""
    metadata = _run_ffprobe(video_path)

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


def analyze_audio(audio_path: Path) -> AudioMetadata:
    """Return typed audio metadata; raises OutputValidationError if no audio."""
    try:
        metadata = _run_ffprobe(audio_path)
    except MediaValidationError as exc:
        raise OutputValidationError(f"AUDIO_OUTPUT_INVALID:{exc.code}")

    audio_stream = next(
        (s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        raise OutputValidationError("AUDIO_OUTPUT_NO_STREAM")

    return AudioMetadata(
        codec=audio_stream.get("codec_name", ""),
        sample_rate=int(audio_stream.get("sample_rate", 0) or 0),
        channels=int(audio_stream.get("channels", 0) or 0),
        duration=float(metadata.get("format", {}).get("duration", 0) or 0),
    )


def verify_video_output(video_path: Path) -> VideoMetadata:
    """Verify a produced video proxy really is a decodable video (retryable)."""
    try:
        return analyze_video(video_path)
    except MediaValidationError as exc:
        raise OutputValidationError(f"NORMALIZED_OUTPUT_INVALID:{exc.code}")


def verify_audio_output(
    audio_path: Path,
    *,
    codec: str = "pcm_s16le",
    sample_rate: int = 16000,
    channels: int = 1,
) -> AudioMetadata:
    """Verify the extracted audio matches the expected PCM/WAV format (retryable)."""
    meta = analyze_audio(audio_path)
    if meta.codec != codec or meta.sample_rate != sample_rate or meta.channels != channels:
        raise OutputValidationError(
            f"AUDIO_OUTPUT_FORMAT:{meta.codec}/{meta.sample_rate}/{meta.channels}"
        )
    return meta
