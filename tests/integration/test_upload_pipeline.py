"""End-to-end pipeline smoke test against real Postgres/MinIO/Temporal with a
real ffmpeg-generated video."""
import pytest
from sqlalchemy import text

from tests.integration.conftest import wait_for_status, derived_objects

pytestmark = pytest.mark.integration


def test_full_pipeline_reaches_done_with_verified_artifacts(
    api, minio, db_engine, cleanup, video_with_audio
):
    path = video_with_audio(3)
    with open(path, "rb") as f:
        resp = api.post("/v1/upload", files={"file": (path.name, f, "video/mp4")})
    assert resp.status_code == 202, resp.text
    aid = resp.json()["asset_id"]
    cleanup(aid)

    final = wait_for_status(api, aid, {"DONE", "FAILED", "NO_AUDIO"}, timeout=120)
    assert final["status"] == "DONE", final
    assert final["progress"] == 100

    steps = {s["step_name"]: s for s in final["steps"]}
    assert set(steps) == {
        "probe",
        "normalize",
        "extract_audio",
        "audio_window_indexing",
        "thumbnail",
        "scene_detection",
        }
    assert all(s["state"] == "COMPLETED" for s in steps.values())

    # media_files: original + proxy + audio + thumbnail
    with db_engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                select mf.file_type from media_files mf
                join media_assets ma on ma.id = mf.video_id
                where ma.asset_id = :aid
                """
            ),
            {"aid": aid},
        ).fetchall()
    assert sorted(r[0] for r in rows) == ["audio", "original", "proxy", "thumbnail"]

    # Derived artifacts exist at the deterministic keys and are non-empty.
    objs = derived_objects(minio, aid)
    assert objs == [
        f"media-derived/{aid}/audio/source.wav",
        f"media-derived/{aid}/proxy/720p.mp4",
        f"media-derived/{aid}/thumbnail/default.jpg",
    ]
    bucket = minio.settings.MINIO_BUCKET
    for key in objs:
        assert minio.client.stat_object(bucket, key).size > 0
