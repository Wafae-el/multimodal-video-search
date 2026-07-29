"""Worker restart durability: stopping the worker mid-processing and restarting
it must not produce duplicate steps or duplicate derived objects."""
import time

import pytest
from sqlalchemy import text

from tests.integration.conftest import wait_for_status, derived_objects

pytestmark = pytest.mark.integration


@pytest.fixture
def worker_container(require_stack):
    try:
        import docker
    except ImportError:
        pytest.skip("docker SDK not installed (pip install docker)")
    try:
        client = docker.from_env()
        container = client.containers.get("video_worker")
        container.reload()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"cannot access video_worker container: {exc}")
    return container


def test_worker_restart_is_idempotent(
    api, minio, db_engine, cleanup, video_with_audio, worker_container
):
    # A larger/longer clip so normalize is still running at the restart point.
    path = video_with_audio(45, size="1280x720", rate=30)
    with open(path, "rb") as f:
        resp = api.post("/v1/upload", files={"file": (path.name, f, "video/mp4")})
    assert resp.status_code == 202, resp.text
    aid = resp.json()["asset_id"]
    cleanup(aid)

    # Wait until an activity is actually in progress, then kill the worker
    # mid-activity (SIGKILL) and restart it.
    for _ in range(20):
        st = api.get(f"/v1/assets/{aid}").json()["status"]
        if st in ("PROBING", "NORMALIZING", "EXTRACTING_AUDIO", "GENERATING_THUMBNAIL"):
            break
        time.sleep(0.5)
    worker_container.stop(timeout=1)  # SIGTERM then quick SIGKILL -> interrupt
    time.sleep(2)
    worker_container.start()

    final = wait_for_status(api, aid, {"DONE", "FAILED"}, timeout=240)
    assert final["status"] == "DONE", final

    # Exactly one processing-step row per operation key, all COMPLETED.
    with db_engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                select ps.operation_key, ps.state, count(*) as c
                from processing_steps ps
                join media_assets ma on ma.id = ps.video_id
                where ma.asset_id = :aid
                group by ps.operation_key, ps.state
                """
            ),
            {"aid": aid},
        ).fetchall()
    assert len(rows) == 4, rows  # four distinct operation keys
    for _op, state, count in rows:
        assert state == "COMPLETED", rows
        assert count == 1, rows

    # Exactly one derived object per role (proxy, audio, thumbnail).
    assert len(derived_objects(minio, aid)) == 3
