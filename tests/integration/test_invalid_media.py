"""Invalid media: uploading non-video bytes yields a stable error code and a
durable FAILED asset record."""
import pytest

pytestmark = pytest.mark.integration


def test_invalid_bytes_persist_failed(api, cleanup):
    resp = api.post(
        "/v1/upload",
        files={"file": ("broken.mp4", b"this is not a video" * 100, "video/mp4")},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["code"] == "MEDIA_CORRUPT"
    aid = body["asset_id"]
    assert aid is not None
    cleanup(aid)

    status = api.get(f"/v1/assets/{aid}").json()
    assert status["status"] == "FAILED"
    assert status["last_error"] == "MEDIA_CORRUPT"
