"""Integration tests for the upload endpoint (Part 4 consistency + Part 5
durable invalid/no-audio states).

Self-contained: MinIO, Temporal and ffprobe are mocked and the database is a
temporary SQLite file, so no external services are required. Run with the
project dependencies installed (fastapi, temporalio, httpx):

    pytest tests/integration/test_upload.py
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from packages.metadata.database import Base, get_db
from packages.metadata import models  # noqa: F401  (register models on Base)
from packages.media.ffprobe_service import VideoMetadata, MediaValidationError
import apps.api.main as main_mod
from apps.api.main import app
from packages.workflow.state_machine import ProcessingState


@pytest.fixture
def ctx(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/upload_test.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db

    # No external services.
    monkeypatch.setattr(main_mod, "create_bucket", lambda: None)
    deleted = []
    monkeypatch.setattr(
        main_mod, "upload_original_video",
        lambda asset_id, path, ext="mp4": {
            "bucket": "media",
            "object_key": f"media-original/{asset_id}/original.{ext}",
        },
    )
    monkeypatch.setattr(main_mod, "delete_object", lambda key: deleted.append(key))

    fake_client = MagicMock()
    fake_client.start_workflow = AsyncMock(return_value=None)
    connect = AsyncMock(return_value=fake_client)
    monkeypatch.setattr(main_mod.Client, "connect", connect)

    with TestClient(app) as client:
        yield {
            "client": client,
            "start_workflow": fake_client.start_workflow,
            "deleted": deleted,
            "monkeypatch": monkeypatch,
        }
    app.dependency_overrides.clear()


def _upload(client, content=b"data", filename="clip.mp4", content_type="video/mp4"):
    return client.post(
        "/v1/upload",
        files={"file": (filename, content, content_type)},
    )


def test_valid_upload_starts_workflow(ctx):
    ctx["monkeypatch"].setattr(
        main_mod, "analyze_video",
        lambda p: VideoMetadata(12.5, 1024, "h264", 1920, 1080, has_audio=True),
    )
    resp = _upload(ctx["client"])
    assert resp.status_code == 202
    body = resp.json()
    asset_id = body["asset_id"]
    assert body["status"] == ProcessingState.UPLOADED.value
    # Deterministic workflow id.
    assert body["workflow_id"] == f"process-asset-{asset_id}-v1"
    ctx["start_workflow"].assert_awaited_once()

    status = ctx["client"].get(f"/v1/assets/{asset_id}").json()
    assert status["status"] == ProcessingState.UPLOADED.value
    assert status["last_error"] is None


def test_no_audio_is_persisted(ctx):
    ctx["monkeypatch"].setattr(
        main_mod, "analyze_video",
        lambda p: VideoMetadata(5.0, 100, "h264", 640, 480, has_audio=False),
    )
    resp = _upload(ctx["client"])
    assert resp.status_code == 422
    body = resp.json()
    # Flat ErrorResponse shape (no nested "detail").
    assert set(body.keys()) == {"error", "code", "asset_id"}
    assert body["code"] == "MEDIA_NO_AUDIO"
    asset_id = body["asset_id"]

    # No workflow started for no-audio media.
    ctx["start_workflow"].assert_not_awaited()

    status = ctx["client"].get(f"/v1/assets/{asset_id}").json()
    assert status["status"] == ProcessingState.NO_AUDIO.value
    assert status["last_error"] == "MEDIA_NO_AUDIO"
    assert status["progress"] == 0


def test_corrupt_media_is_persisted_as_failed(ctx):
    def raise_corrupt(p):
        raise MediaValidationError("CORRUPT_MEDIA")

    ctx["monkeypatch"].setattr(main_mod, "analyze_video", raise_corrupt)
    resp = _upload(ctx["client"])
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "MEDIA_CORRUPT"
    asset_id = body["asset_id"]

    status = ctx["client"].get(f"/v1/assets/{asset_id}").json()
    assert status["status"] == ProcessingState.FAILED.value
    assert status["last_error"] == "MEDIA_CORRUPT"
    ctx["start_workflow"].assert_not_awaited()


def test_missing_video_stream_maps_to_stable_code(ctx):
    def raise_no_video(p):
        raise MediaValidationError("MISSING_VIDEO_STREAM")

    ctx["monkeypatch"].setattr(main_mod, "analyze_video", raise_no_video)
    resp = _upload(ctx["client"])
    assert resp.status_code == 422
    assert resp.json()["code"] == "MEDIA_NO_VIDEO_STREAM"


def test_unsupported_mime_rejected_without_record(ctx):
    resp = _upload(ctx["client"], content_type="text/plain", filename="a.txt")
    assert resp.status_code == 415
    body = resp.json()
    assert body["code"] == "MEDIA_UNSUPPORTED"
    assert body["asset_id"] is None


def test_too_large_rejected(ctx):
    ctx["monkeypatch"].setattr(main_mod, "MAX_SIZE", 4)
    resp = _upload(ctx["client"], content=b"way too big")
    assert resp.status_code == 413
    assert resp.json()["code"] == "MEDIA_TOO_LARGE"


def test_duration_exceeded_persisted(ctx):
    ctx["monkeypatch"].setattr(main_mod, "MAX_DURATION", 10)
    ctx["monkeypatch"].setattr(
        main_mod, "analyze_video",
        lambda p: VideoMetadata(999.0, 1024, "h264", 1920, 1080, has_audio=True),
    )
    resp = _upload(ctx["client"])
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "MEDIA_DURATION_EXCEEDED"
    status = ctx["client"].get(f"/v1/assets/{body['asset_id']}").json()
    assert status["status"] == ProcessingState.FAILED.value
    assert status["last_error"] == "MEDIA_DURATION_EXCEEDED"


def test_workflow_dispatch_failure_is_recoverable(ctx):
    ctx["monkeypatch"].setattr(
        main_mod, "analyze_video",
        lambda p: VideoMetadata(12.5, 1024, "h264", 1920, 1080, has_audio=True),
    )
    ctx["monkeypatch"].setattr(
        main_mod.Client, "connect",
        AsyncMock(side_effect=RuntimeError("temporal down")),
    )
    resp = _upload(ctx["client"])
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "WORKFLOW_DISPATCH_FAILED"
    asset_id = body["asset_id"]

    # Recoverable: asset stays UPLOADED with a deterministic workflow id and a
    # persisted last_error, so a retry can safely re-dispatch.
    status = ctx["client"].get(f"/v1/assets/{asset_id}").json()
    assert status["status"] == ProcessingState.UPLOADED.value
    assert status["last_error"] == "WORKFLOW_DISPATCH_FAILED"
