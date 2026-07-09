import json
import subprocess
from pathlib import Path


def analyze_video(video_path: Path) -> dict:
    """
    Analyze a video using ffprobe and return its metadata.
    """

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
        check=True,
    )

    return json.loads(result.stdout)