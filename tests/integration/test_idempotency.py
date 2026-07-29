"""Retry-safety and production-idempotency tests (Parts 6 & 7).

Self-contained: MinIO and the FFmpeg/ffprobe steps are mocked and the database
is a temporary SQLite file. Activities are executed through Temporal's
``ActivityEnvironment`` so ``activity.info()`` / ``activity.logger`` work.
"""
import dataclasses
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from temporalio.testing import ActivityEnvironment
from temporalio.exceptions import ApplicationError

import packages.metadata.database as database
from packages.metadata.database import Base
from packages.metadata.models import Video, ProcessingStep
from packages.media.ffprobe_service import VideoMetadata, MediaValidationError
from packages.storage.minio_service import build_proxy_object_key
from packages.workflow.contracts import ProcessAssetInput, ACTIVITY_MAX_ATTEMPTS
from packages.workflow.state_machine import ProcessingState
import packages.workflow.activities as activities


def run_activity(fn, inp, env=None):
    """Run a (synchronous) activity through an ActivityEnvironment."""
    env = env or ActivityEnvironment()
    return env.run(fn, inp)


@pytest.fixture
def env(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/idem.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    # Activities use get_session() -> database.SessionLocal.
    monkeypatch.setattr(database, "SessionLocal", Session)

    asset_id = str(uuid.uuid4())
    with Session() as db:
        db.add(Video(
            asset_id=asset_id,
            filename="clip.mp4",
            content_type="video/mp4",
            source_checksum="chk-1",
            pipeline_version="v1",
            minio_bucket="media",
            minio_object_key=f"media-original/{asset_id}/original.mp4",
            status=ProcessingState.UPLOADED.value,
            progress=0,
            attempts=0,
        ))
        db.commit()

    # No real storage, original download, or ffprobe output verification.
    monkeypatch.setattr(activities, "object_exists", lambda key: True)
    monkeypatch.setattr(activities, "verify_video_output", lambda p: None)
    monkeypatch.setattr(activities, "verify_audio_output", lambda p: None)
    monkeypatch.setattr(
        activities, "download_original_video",
        lambda info, workdir: (Path(workdir) / "original").write_bytes(b"x") or (Path(workdir) / "original"),
    )

    return {"asset_id": asset_id, "Session": Session, "monkeypatch": monkeypatch}


def _set_status(Session, asset_id, status):
    with Session() as db:
        db.query(Video).filter(Video.asset_id == asset_id).update({"status": status})
        db.commit()


def _get(Session, asset_id):
    with Session() as db:
        return db.query(Video).filter(Video.asset_id == asset_id).first()


def _steps(Session):
    with Session() as db:
        return db.query(ProcessingStep).all()


def _mock_normalize(monkeypatch):
    def fake_ffmpeg(src, out):
        Path(out).write_bytes(b"proxy-bytes")
    ffmpeg = MagicMock(side_effect=fake_ffmpeg)
    monkeypatch.setattr(activities, "normalize_video_file", ffmpeg)
    return ffmpeg


def test_repeated_activity_reuses_output(env):
    """One DB result, one artifact, FFmpeg invoked once (Part 7 acceptance)."""
    Session, asset_id, mp = env["Session"], env["asset_id"], env["monkeypatch"]
    proxy_key = build_proxy_object_key(asset_id)
    ffmpeg = _mock_normalize(mp)
    upload = MagicMock(return_value={"bucket": "media", "object_key": proxy_key})
    mp.setattr(activities, "upload_normalized_video", upload)

    inp = ProcessAssetInput(asset_id=asset_id, pipeline_version="v1")

    r1 = run_activity(activities.normalize_video, inp)
    assert r1["reused"] is False
    assert ffmpeg.call_count == 1
    assert upload.call_count == 1

    # Second delivery: reuse, no FFmpeg, no upload.
    r2 = run_activity(activities.normalize_video, inp)
    assert r2["reused"] is True
    assert ffmpeg.call_count == 1
    assert upload.call_count == 1

    steps = _steps(Session)
    assert len(steps) == 1
    assert steps[0].state == "COMPLETED"
    assert steps[0].output_key == proxy_key
    assert steps[0].output_bucket == "media"

    asset = _get(Session, asset_id)
    assert asset.status == ProcessingState.EXTRACTING_AUDIO.value
    assert asset.progress == 50


def test_retry_after_state_advanced_does_not_raise(env):
    """A retried probe when the asset is already at NORMALIZING must not raise an
    invalid-transition error (Part 6 acceptance)."""
    Session, asset_id, mp = env["Session"], env["asset_id"], env["monkeypatch"]
    _set_status(Session, asset_id, ProcessingState.NORMALIZING.value)
    mp.setattr(
        activities, "analyze_video",
        lambda p: VideoMetadata(10.0, 100, "h264", 1280, 720, has_audio=True),
    )

    run_activity(
        activities.probe_video,
        ProcessAssetInput(asset_id=asset_id, pipeline_version="v1"),
    )

    asset = _get(Session, asset_id)
    # Never moved backwards; still at (or past) NORMALIZING.
    assert asset.status == ProcessingState.NORMALIZING.value


def test_retryable_failure_is_not_terminal_until_exhausted(env):
    Session, asset_id, mp = env["Session"], env["asset_id"], env["monkeypatch"]
    mp.setattr(activities, "upload_normalized_video",
               MagicMock(return_value={"bucket": "media", "object_key": "k"}))
    mp.setattr(activities, "normalize_video_file",
               MagicMock(side_effect=RuntimeError("boom")))
    inp = ProcessAssetInput(asset_id=asset_id, pipeline_version="v1")

    # Attempt 1 (default): retryable -> not terminal.
    with pytest.raises(Exception):
        run_activity(activities.normalize_video, inp)
    asset = _get(Session, asset_id)
    assert asset.status != ProcessingState.FAILED.value
    assert asset.last_error is not None
    assert _steps(Session)[0].state == "FAILED"

    # Final attempt: retries exhausted -> terminal FAILED.
    env_last = ActivityEnvironment()
    env_last.info = dataclasses.replace(env_last.info, attempt=ACTIVITY_MAX_ATTEMPTS)
    with pytest.raises(Exception):
        run_activity(activities.normalize_video, inp, env_last)
    asset = _get(Session, asset_id)
    assert asset.status == ProcessingState.FAILED.value
    assert asset.last_error is not None
    # Still exactly one step row (idempotent identity).
    assert len(_steps(Session)) == 1


def test_media_validation_error_is_non_retryable_and_terminal(env):
    Session, asset_id, mp = env["Session"], env["asset_id"], env["monkeypatch"]

    def raise_corrupt(p):
        raise MediaValidationError("CORRUPT_MEDIA")

    mp.setattr(activities, "analyze_video", raise_corrupt)

    with pytest.raises(ApplicationError) as exc:
        run_activity(
            activities.probe_video,
            ProcessAssetInput(asset_id=asset_id, pipeline_version="v1"),
        )
    assert exc.value.non_retryable is True

    asset = _get(Session, asset_id)
    assert asset.status == ProcessingState.FAILED.value
    assert asset.last_error == "CORRUPT_MEDIA"


def test_precompleted_step_is_reused_without_ffmpeg(env):
    """A COMPLETED step whose artifact exists is reused (duplicate delivery)."""
    Session, asset_id, mp = env["Session"], env["asset_id"], env["monkeypatch"]
    proxy_key = build_proxy_object_key(asset_id)

    from packages.workflow.operation_key import build_operation_key
    op_key = build_operation_key("chk-1", "normalize", "v1", "ffmpeg-normalizer-v1")
    with Session() as db:
        asset = db.query(Video).filter(Video.asset_id == asset_id).first()
        db.add(ProcessingStep(
            video_id=asset.id, step_name="normalize", step_version="v1",
            tool_version="ffmpeg-normalizer-v1", input_checksum="chk-1",
            operation_key=op_key, state="COMPLETED",
            output_bucket="media", output_key=proxy_key, output_checksum="c", attempts=1,
        ))
        db.commit()

    ffmpeg = _mock_normalize(mp)
    mp.setattr(activities, "upload_normalized_video", MagicMock())

    r = run_activity(
        activities.normalize_video,
        ProcessAssetInput(asset_id=asset_id, pipeline_version="v1"),
    )
    assert r["reused"] is True
    assert ffmpeg.call_count == 0
    assert len(_steps(Session)) == 1


def test_attempts_increment_on_retry_not_on_reuse(env):
    """Forced retry raises the attempt count; reusing a completed result does not
    (Part 8 acceptance)."""
    Session, asset_id, mp = env["Session"], env["asset_id"], env["monkeypatch"]
    proxy_key = build_proxy_object_key(asset_id)
    mp.setattr(activities, "upload_normalized_video",
               MagicMock(return_value={"bucket": "media", "object_key": proxy_key}))

    inp = ProcessAssetInput(asset_id=asset_id, pipeline_version="v1")

    # First execution fails -> step.attempts == 1, asset.attempts == 1.
    mp.setattr(activities, "normalize_video_file", MagicMock(side_effect=RuntimeError("x")))
    with pytest.raises(Exception):
        run_activity(activities.normalize_video, inp)
    assert _steps(Session)[0].attempts == 1
    assert _get(Session, asset_id).attempts == 1

    # Forced retry (resume) succeeds -> attempts advanced to 2.
    _mock_normalize(mp)  # now writes the proxy and succeeds
    run_activity(activities.normalize_video, inp)
    assert _steps(Session)[0].attempts == 2
    assert _get(Session, asset_id).attempts == 2

    # Duplicate retrieval of the completed result -> attempts unchanged.
    run_activity(activities.normalize_video, inp)
    assert _steps(Session)[0].attempts == 2
    assert _get(Session, asset_id).attempts == 2
