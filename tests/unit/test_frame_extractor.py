from pathlib import Path

from packages.media.frame_extractor import FrameExtractor


def test_extract_calls_ffmpeg(monkeypatch):
    called = {}

    def fake_run(cmd, check, capture_output):
        called["cmd"] = cmd

    monkeypatch.setattr(
        "packages.media.frame_extractor.subprocess.run",
        fake_run,
    )

    extractor = FrameExtractor()

    output = extractor.extract(
        Path("video.mp4"),
        5000,
        Path("frame.jpg"),
    )

    assert output == Path("frame.jpg")

    cmd = called["cmd"]

    assert cmd[0] == "ffmpeg"
    assert "-ss" in cmd
    assert "5.0" in cmd
    assert str(Path("video.mp4")) in cmd
    assert str(Path("frame.jpg")) in cmd