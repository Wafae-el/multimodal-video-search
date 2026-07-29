"""Duplicate delivery: invoking the same activity/operation twice against real
services must run FFmpeg once and leave exactly one step row and one object."""
import hashlib
import uuid

import pytest
from sqlalchemy import text
from temporalio.testing import ActivityEnvironment

import packages.workflow.activities as activities
from packages.metadata.models import Video
from packages.workflow.contracts import ProcessAssetInput

pytestmark = pytest.mark.integration


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def test_duplicate_activity_delivery_is_idempotent(
    minio, db_session, db_engine, cleanup, video_with_audio
):
    path = video_with_audio(3)
    asset_id = str(uuid.uuid4())
    cleanup(asset_id)

    # Seed a real original object + asset row.
    upload = minio.upload_original_video(asset_id, path)
    checksum = _sha256(path)
    asset = Video(
        asset_id=asset_id,
        filename="clip.mp4",
        content_type="video/mp4",
        source_checksum=checksum,
        pipeline_version="v1",
        minio_bucket=upload["bucket"],
        minio_object_key=upload["object_key"],
        status="UPLOADED",
        progress=0,
        attempts=0,
    )
    db_session.add(asset)
    db_session.commit()

    inp = ProcessAssetInput(asset_id=asset_id, pipeline_version="v1")

    # First delivery does the real work.
    r1 = ActivityEnvironment().run(activities.normalize_video, inp)
    assert r1["reused"] is False

    # Second (duplicate) delivery reuses the stored output — no FFmpeg re-run.
    r2 = ActivityEnvironment().run(activities.normalize_video, inp)
    assert r2["reused"] is True
    assert r1["output_key"] == r2["output_key"]

    # Exactly one completed normalize step.
    with db_engine.begin() as conn:
        count = conn.execute(
            text(
                """
                select count(*) from processing_steps ps
                join media_assets ma on ma.id = ps.video_id
                where ma.asset_id = :aid and ps.step_name = 'normalize'
                  and ps.state = 'COMPLETED'
                """
            ),
            {"aid": asset_id},
        ).scalar()
    assert count == 1

    # Exactly one proxy object.
    bucket = minio.settings.MINIO_BUCKET
    proxies = list(
        minio.client.list_objects(
            bucket, prefix=f"media-derived/{asset_id}/proxy/", recursive=True
        )
    )
    assert len(proxies) == 1
