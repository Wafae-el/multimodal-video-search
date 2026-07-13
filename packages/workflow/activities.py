from temporalio import activity
from packages.metadata.database import get_session
from packages.metadata.crud import update_video_status

@activity.defn
async def validate_asset(asset: dict) -> dict:

    db = get_session()

    update_video_status(
        db=db,
        video_id=asset["video_id"],
        status="VALIDATING",
        progress=20,
    )

    print(f"[Validate] {asset['filename']}")

    db.close()

    return asset


@activity.defn
async def probe_video(asset: dict) -> dict:

    db = get_session()

    update_video_status(
        db=db,
        video_id=asset["video_id"],
        status="PROBING",
        progress=40,
    )

    print(f"[Probe] {asset['filename']}")

    db.close()

    return asset


@activity.defn
async def normalize_video(asset: dict) -> dict:

    db = get_session()

    update_video_status(
        db=db,
        video_id=asset["video_id"],
        status="NORMALIZING",
        progress=60,
    )

    print(f"[Normalize] {asset['filename']}")

    db.close()

    return asset


@activity.defn
async def extract_audio(asset: dict) -> dict:

    db = get_session()

    update_video_status(
        db=db,
        video_id=asset["video_id"],
        status="EXTRACTING_AUDIO",
        progress=80,
    )

    print(f"[Extract Audio] {asset['filename']}")

    db.close()

    return asset


@activity.defn
async def generate_thumbnail(asset: dict) -> dict:

    db = get_session()

    update_video_status(
        db=db,
        video_id=asset["video_id"],
        status="DONE",
        progress=100,
    )

    print(f"[Thumbnail] {asset['filename']}")

    db.close()

    return asset