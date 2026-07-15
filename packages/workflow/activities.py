from pathlib import Path

from temporalio import activity

from packages.workflow.state_machine import ProcessingState
from packages.metadata.database import get_session
from packages.metadata.crud import update_video_status


@activity.defn
async def validate_asset(asset: dict) -> dict:

    db = get_session()

    update_video_status(
        db=db,
        video_id=asset["video_id"],
        status=ProcessingState.VALIDATING.value,
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
        status=ProcessingState.PROBING.value,
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
        status=ProcessingState.NORMALIZING.value,
        progress=60,
    )

    print(f"[Normalize] {asset['filename']}")

    db.close()

    return asset


@activity.defn
async def detect_scenes_activity(asset: dict) -> dict:

    from packages.segmentation.scene_detector import detect_scenes

    print(f"[Scene Detection] {asset['filename']}")

    video_path = Path("temp") / asset["filename"]

    scenes = detect_scenes(video_path)

    asset["scenes"] = scenes

    print(f"Detected {len(scenes)} scenes")

    return asset


@activity.defn
async def extract_frames_activity(asset: dict) -> dict:

    from packages.segmentation.frame_extractor import (
        extract_representative_frames,
    )

    print(f"[Representative Frames] {asset['filename']}")

    video_path = Path("temp") / asset["filename"]

    frames = extract_representative_frames(
        video_path,
        asset["scenes"],
        Path("frames"),
    )

    asset["frames"] = frames

    print(f"Extracted {len(frames)} frames")

    return asset


@activity.defn
async def extract_audio(asset: dict) -> dict:

    from packages.segmentation.audio_extractor import (
        extract_audio as extract_audio_file,
    )

    db = get_session()

    update_video_status(
        db=db,
        video_id=asset["video_id"],
        status=ProcessingState.EXTRACTING_AUDIO.value,
        progress=80,
    )

    video_path = Path("temp") / asset["filename"]

    audio_path = extract_audio_file(
        video_path,
        Path("audio"),
    )

    asset["audio"] = str(audio_path)

    print(f"[Extract Audio] {audio_path}")

    db.close()

    return asset


@activity.defn
async def generate_thumbnail(asset: dict) -> dict:

    db = get_session()

    update_video_status(
        db=db,
        video_id=asset["video_id"],
        status=ProcessingState.DONE.value,
        progress=100,
    )

    print(f"[Thumbnail] {asset['filename']}")

    db.close()

    return asset