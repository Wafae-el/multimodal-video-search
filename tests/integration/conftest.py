"""Fixtures for real-service integration tests (Part 11).

These tests talk to real PostgreSQL, MinIO and Temporal. They are skipped unless
``INTEGRATION=1`` is set and the stack is reachable, so the default unit run
(which also lives under tests/integration for the self-contained upload /
idempotency suites) stays green.

Intended to run inside a container attached to the compose network, e.g.:

    docker run --rm --network infrastructure_default \
      -v "$PWD:/app" -w /app \
      -v //var/run/docker.sock:/var/run/docker.sock \
      -e INTEGRATION=1 \
      -e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/video_search \
      -e MINIO_ENDPOINT=minio:9000 -e MINIO_ACCESS_KEY=minioadmin \
      -e MINIO_SECRET_KEY=minioadmin -e MINIO_BUCKET=media \
      -e TEMPORAL_ADDRESS=temporal:7233 -e QDRANT_URL=http://qdrant:6333 \
      -e API_BASE_URL=http://api:8000 \
      <image> sh -c "pip install -q docker && pytest tests/integration -m integration"
"""
import os
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

INTEGRATION = os.environ.get("INTEGRATION") == "1"
API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")


def _stack_reachable() -> bool:
    try:
        httpx.get(f"{API_BASE_URL}/", timeout=3.0)
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def require_stack():
    if not INTEGRATION:
        pytest.skip("integration tests require INTEGRATION=1 and a running stack")
    if not _stack_reachable():
        pytest.skip(f"stack not reachable at {API_BASE_URL}")


@pytest.fixture(scope="session")
def db_engine(require_stack):
    from packages.config.settings import settings
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def minio(require_stack):
    from packages.storage import minio_service
    minio_service.create_bucket()
    return minio_service


@pytest.fixture
def api(require_stack):
    with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


# ---- Cleanup ---------------------------------------------------------------
@pytest.fixture
def cleanup(db_engine, minio):
    """Track created asset ids and remove their DB rows and MinIO objects,
    so tests are repeatable and order-independent."""
    asset_ids: list[str] = []

    def _track(asset_id: str):
        asset_ids.append(asset_id)
        return asset_id

    yield _track

    bucket = minio.settings.MINIO_BUCKET
    for aid in asset_ids:
        for prefix in (f"media-original/{aid}/", f"media-derived/{aid}/"):
            try:
                for obj in minio.client.list_objects(bucket, prefix=prefix, recursive=True):
                    minio.client.remove_object(bucket, obj.object_name)
            except Exception:
                pass
        try:
            with db_engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM media_assets WHERE asset_id = :aid"),
                    {"aid": aid},
                )
        except Exception:
            pass


# ---- Real ffmpeg media generators -----------------------------------------
def _ffmpeg(args: list[str]) -> None:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", *args],
        check=True,
        capture_output=True,
        timeout=120,
    )


@pytest.fixture
def video_with_audio(tmp_path):
    def _make(duration: int = 3, size: str = "320x240", rate: int = 15) -> Path:
        out = tmp_path / f"withaudio_{uuid.uuid4().hex}.mp4"
        _ffmpeg([
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size={size}:rate={rate}",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            str(out),
        ])
        return out
    return _make


@pytest.fixture
def video_no_audio(tmp_path):
    def _make(duration: int = 2) -> Path:
        out = tmp_path / f"noaudio_{uuid.uuid4().hex}.mp4"
        _ffmpeg([
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x240:rate=15",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
        ])
        return out
    return _make


# ---- Helpers ---------------------------------------------------------------
def wait_for_status(api_client, asset_id, targets, timeout=90.0, interval=2.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = api_client.get(f"/v1/assets/{asset_id}")
        last = resp.json()
        if last["status"] in targets:
            return last
        time.sleep(interval)
    raise AssertionError(f"asset {asset_id} did not reach {targets}; last={last}")


def derived_objects(minio, asset_id):
    bucket = minio.settings.MINIO_BUCKET
    return sorted(
        o.object_name
        for o in minio.client.list_objects(
            bucket, prefix=f"media-derived/{asset_id}/", recursive=True
        )
    )
