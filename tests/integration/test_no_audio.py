"""No-audio: a valid video without an audio stream yields a durable NO_AUDIO
asset record (real ffmpeg-generated input)."""
import pytest

pytestmark = pytest.mark.integration


def test_no_audio_video_persists_no_audio(api, cleanup, video_no_audio):
    path = video_no_audio(2)
    with open(path, "rb") as f:
        resp = api.post("/v1/upload", files={"file": (path.name, f, "video/mp4")})
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "MEDIA_NO_AUDIO"
    aid = body["asset_id"]
    assert aid is not None
    cleanup(aid)

    status = api.get(f"/v1/assets/{aid}").json()
    assert status["status"] == "NO_AUDIO"
    assert status["last_error"] == "MEDIA_NO_AUDIO"
    assert status["progress"] == 0
