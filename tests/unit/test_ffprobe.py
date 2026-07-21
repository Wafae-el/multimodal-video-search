import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.media.ffprobe_service import (
    MediaValidationError,
    VideoMetadata,
    analyze_video,
)


@patch("packages.media.ffprobe_service.subprocess.run")
def test_valid_ffprobe_response(mock_run):
    mock_run.return_value.stdout = json.dumps(
        {
            "format": {
                "duration": "12.5",
                "size": "1024",
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                },
            ],
        }
    )

    metadata = analyze_video(Path("video.mp4"))

    assert isinstance(metadata, VideoMetadata)
    assert metadata.duration == 12.5
    assert metadata.size == 1024
    assert metadata.video_codec == "h264"
    assert metadata.width == 1920
    assert metadata.height == 1080
    assert metadata.has_audio is True


@patch("packages.media.ffprobe_service.subprocess.run")
def test_no_audio_stream(mock_run):
    mock_run.return_value.stdout = json.dumps(
        {
            "format": {
                "duration": "5",
                "size": "100",
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 640,
                    "height": 480,
                }
            ],
        }
    )

    metadata = analyze_video(Path("video.mp4"))

    assert metadata.has_audio is False


@patch("packages.media.ffprobe_service.subprocess.run")
def test_missing_video_stream(mock_run):
    mock_run.return_value.stdout = json.dumps(
        {
            "format": {
                "duration": "5",
                "size": "100",
            },
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                }
            ],
        }
    )

    with pytest.raises(MediaValidationError) as exc:
        analyze_video(Path("video.mp4"))

    assert exc.value.code == "MISSING_VIDEO_STREAM"


@patch("packages.media.ffprobe_service.subprocess.run")
def test_corrupt_media(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

    with pytest.raises(MediaValidationError) as exc:
        analyze_video(Path("video.mp4"))

    assert exc.value.code == "CORRUPT_MEDIA"


@patch("packages.media.ffprobe_service.subprocess.run")
def test_timeout(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 30)

    with pytest.raises(MediaValidationError) as exc:
        analyze_video(Path("video.mp4"))

    assert exc.value.code == "FFPROBE_TIMEOUT"


@patch("packages.media.ffprobe_service.subprocess.run")
def test_malformed_json(mock_run):
    mock_run.return_value.stdout = "{invalid json}"

    with pytest.raises(MediaValidationError) as exc:
        analyze_video(Path("video.mp4"))

    assert exc.value.code == "UNSUPPORTED_MEDIA"


@patch("packages.media.ffprobe_service.subprocess.run")
def test_ffprobe_unavailable(mock_run):
    mock_run.side_effect = FileNotFoundError

    with pytest.raises(MediaValidationError) as exc:
        analyze_video(Path("video.mp4"))

    assert exc.value.code == "FFPROBE_UNAVAILABLE"