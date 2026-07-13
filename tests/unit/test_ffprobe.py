from pathlib import Path

from packages.media.ffprobe_service import analyze_video


def test_ffprobe():

    sample = Path("temp")

    assert sample.exists()