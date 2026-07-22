import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from temporalio import activity

from packages.config.settings import settings
from packages.metadata.database import get_session
from packages.metadata.crud import (
    get_asset_status,
    start_processing_step,
    complete_processing_step,
    fail_processing_step,
    reuse_completed_operation,
)
from packages.media.ffprobe_service import (
    analyze_video,
    MediaValidationError,
)
from packages.media.normalizer import normalize_video as normalize_video_file
from packages.media.thumbnail_service import generate_thumbnail as generate_thumbnail_file
from packages.segmentation.audio_extractor import extract_audio as extract_audio_file
from packages.storage.minio_service import (
    download_file,
    upload_thumbnail,
    upload_normalized_video,
)
from packages.workflow.state_machine import ProcessingState, ProcessingEvent, next_state


PIPELINE_VERSION = "v1"
WORKSPACE_ROOT = Path("workspace")
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

# Utilisé dans extract_audio et generate_thumbnail
DERIVED_BUCKET = getattr(settings, "DERIVED_BUCKET", "media-derived")


@dataclass
class AssetInfo:
    """Objet immuable contenant les seules données nécessaires."""
    id: int
    asset_id: str
    source_checksum: str
    pipeline_version: str
    minio_bucket: str
    minio_object_key: str


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            digest.update(chunk)
    return digest.hexdigest()


def build_operation_key(checksum: str, step: str, version: str, tool_version: str) -> str:
    """
    Clé canonique basée sur un dictionnaire trié, pour éviter les collisions.
    """
    data = {
        "checksum": checksum,
        "step": step,
        "version": version,
        "tool_version": tool_version,
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def workspace(asset_id: str) -> Path:
    path = WORKSPACE_ROOT / asset_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_original_video(asset_info: AssetInfo) -> Path:
    root = workspace(asset_info.asset_id)
    local_video = root / "original.mp4"
    # Appel avec 2 paramètres : object_key et destination (le bucket est déjà configuré dans minio_service)
    download_file(asset_info.minio_object_key, local_video)
    return local_video


def begin_step(asset_info: AssetInfo, step_name: str, tool_version: str = "1.0"):
    operation_key = build_operation_key(
        asset_info.source_checksum,
        step_name,
        asset_info.pipeline_version,
        tool_version,
    )
    with get_session() as db:
        existing = reuse_completed_operation(db, operation_key)
        if existing:
            return (
                operation_key,
                {
                    "output_key": existing.output_key,
                    "output_checksum": existing.output_checksum,
                },
            )

        start_processing_step(
            db=db,
            video_id=asset_info.id,
            step_name=step_name,
            step_version=asset_info.pipeline_version,
            operation_key=operation_key,
        )
    return (operation_key, None)


def finish_step(operation_key, checksum, object_key):
    with get_session() as db:
        complete_processing_step(db, operation_key, object_key, checksum)


def fail_step(operation_key, error):
    with get_session() as db:
        fail_processing_step(db, operation_key, str(error))

def update_asset_state(asset_id: str, event: ProcessingEvent, progress: int = None, error: str = None):
    """
    Applique la transition d'état définie dans la machine à états,
    puis met à jour l'asset en base.
    """
    with get_session() as db:
        asset = get_asset_status(db, asset_id)
        if asset is None:
            raise RuntimeError(f"Asset {asset_id} not found")

        current_state = ProcessingState(asset.status)
        try:
            new_state = next_state(current_state, event)
        except ValueError as e:
            activity.logger.error(f"Invalid transition: {current_state} + {event} for asset {asset_id}")
            raise

        asset.status = new_state.value
        if progress is not None:
            asset.progress = progress
        if error is not None:
            asset.last_error = error
        else:
            asset.last_error = None

        activity.logger.info(f"Asset {asset_id} transitioned from {current_state.value} to {new_state.value} via {event.value}")


# ---------- Activités ----------
@activity.defn
async def probe_video(asset_input: dict) -> dict:
    """
    Validate the original media and persist the probing result.
    This activity is idempotent.
    """
    activity.logger.info(f"Starting probe_video for asset {asset_input['asset_id']}")

    with get_session() as db:
        asset = get_asset_status(db, asset_input["asset_id"])
        if asset is None:
            raise RuntimeError("ASSET_NOT_FOUND")
        asset_info = AssetInfo(
            id=asset.id,
            asset_id=asset.asset_id,
            source_checksum=asset.source_checksum,
            pipeline_version=asset.pipeline_version,
            minio_bucket=asset.minio_bucket,
            minio_object_key=asset.minio_object_key,
        )

    # --- Correction 2 : deux transitions successives pour respecter la machine ---
    # UPLOADED --UPLOAD_COMPLETE--> VALIDATING --VALIDATION_OK--> PROBING
    update_asset_state(asset_info.asset_id, ProcessingEvent.UPLOAD_COMPLETE)
    update_asset_state(asset_info.asset_id, ProcessingEvent.VALIDATION_OK)

    operation_key, existing = begin_step(
        asset_info,
        "probe",
        tool_version="ffprobe-1",
    )

    if existing:
        activity.logger.info(f"Probe step already completed for asset {asset_info.asset_id}, reusing result")
        update_asset_state(asset_info.asset_id, ProcessingEvent.PROBE_OK)
        return {
            "asset_id": asset_info.asset_id,
            "pipeline_version": asset_info.pipeline_version,
            "probe_checksum": existing["output_checksum"],
            "probe_key": existing["output_key"],
        }

    try:
        local_video = download_original_video(asset_info)
        metadata = analyze_video(local_video)

        probe_file = workspace(asset_info.asset_id) / "probe.json"
        probe_file.write_text(
            "{\n"
            f'  "duration": {metadata.duration},\n'
            f'  "codec": "{metadata.video_codec}",\n'
            f'  "width": {metadata.width},\n'
            f'  "height": {metadata.height},\n'
            f'  "has_audio": {str(metadata.has_audio).lower()}\n'
            "}"
        )

        checksum = sha256_file(probe_file)
        finish_step(operation_key, checksum, None)

        update_asset_state(asset_info.asset_id, ProcessingEvent.PROBE_OK)

        activity.logger.info(f"Probe successful for asset {asset_info.asset_id}")
        return {
            "asset_id": asset_info.asset_id,
            "pipeline_version": asset_info.pipeline_version,
            "probe_checksum": checksum,
            "probe_key": None,
        }

    except MediaValidationError as exc:
        activity.logger.error(f"Media validation error for asset {asset_info.asset_id}: {exc.code}")
        fail_step(operation_key, exc.code)
        update_asset_state(asset_info.asset_id, ProcessingEvent.ERROR, error=exc.code)
        raise

    except Exception as exc:
        activity.logger.error(f"Unexpected error in probe_video for asset {asset_info.asset_id}: {exc}")
        fail_step(operation_key, str(exc))
        update_asset_state(asset_info.asset_id, ProcessingEvent.ERROR, error=str(exc))
        raise
    finally:
        work_dir = workspace(asset_info.asset_id)
        shutil.rmtree(work_dir, ignore_errors=True)


@activity.defn
async def normalize_video(asset_input: dict) -> dict:
    """
    Normalize the original video into a standard MP4 format.
    This activity is idempotent.
    """
    activity.logger.info(f"Starting normalize_video for asset {asset_input['asset_id']}")

    with get_session() as db:
        asset = get_asset_status(db, asset_input["asset_id"])
        if asset is None:
            raise RuntimeError("ASSET_NOT_FOUND")
        asset_info = AssetInfo(
            id=asset.id,
            asset_id=asset.asset_id,
            source_checksum=asset.source_checksum,
            pipeline_version=asset.pipeline_version,
            minio_bucket=asset.minio_bucket,
            minio_object_key=asset.minio_object_key,
        )

    operation_key, existing = begin_step(
        asset_info,
        "normalize",
        tool_version="ffmpeg-normalizer-v1",
    )

    if existing:
        activity.logger.info(f"Normalize step already completed for asset {asset_info.asset_id}, reusing result")
        update_asset_state(asset_info.asset_id, ProcessingEvent.NORMALIZE_OK, progress=50)
        return {
            "asset_id": asset_info.asset_id,
            "pipeline_version": asset_info.pipeline_version,
            "normalized_key": existing["output_key"],
            "normalized_checksum": existing["output_checksum"],
        }

    try:
        local_video = download_original_video(asset_info)
        output_dir = workspace(asset_info.asset_id)
        normalized_path = output_dir / "normalized.mp4"
        normalize_video_file(local_video, normalized_path)

        checksum = sha256_file(normalized_path)
        upload = upload_normalized_video(asset_info.asset_id, normalized_path)

        finish_step(operation_key, checksum, upload["object_key"])

        update_asset_state(asset_info.asset_id, ProcessingEvent.NORMALIZE_OK, progress=50)

        activity.logger.info(f"Normalize successful for asset {asset_info.asset_id}")
        return {
            "asset_id": asset_info.asset_id,
            "pipeline_version": asset_info.pipeline_version,
            "normalized_key": upload["object_key"],
            "normalized_checksum": checksum,
        }

    except Exception as exc:
        activity.logger.error(f"Error in normalize_video for asset {asset_info.asset_id}: {exc}")
        fail_step(operation_key, str(exc))
        update_asset_state(asset_info.asset_id, ProcessingEvent.ERROR, error=str(exc))
        raise
    finally:
        work_dir = workspace(asset_info.asset_id)
        shutil.rmtree(work_dir, ignore_errors=True)


@activity.defn
async def extract_audio(asset_input: dict) -> dict:
    """
    Extract PCM mono 16 kHz WAV audio from the normalized video.
    This activity is idempotent.
    """
    activity.logger.info(f"Starting extract_audio for asset {asset_input['asset_id']}")

    with get_session() as db:
        asset = get_asset_status(db, asset_input["asset_id"])
        if asset is None:
            raise RuntimeError("ASSET_NOT_FOUND")
        asset_info = AssetInfo(
            id=asset.id,
            asset_id=asset.asset_id,
            source_checksum=asset.source_checksum,
            pipeline_version=asset.pipeline_version,
            minio_bucket=asset.minio_bucket,
            minio_object_key=asset.minio_object_key,
        )

    operation_key, existing = begin_step(
        asset_info,
        "extract_audio",
        tool_version="ffmpeg-audio-v1",
    )

    if existing:
        activity.logger.info(f"Extract_audio step already completed for asset {asset_info.asset_id}, reusing result")
        update_asset_state(asset_info.asset_id, ProcessingEvent.AUDIO_OK, progress=90)
        return {
            "asset_id": asset_info.asset_id,
            "pipeline_version": asset_info.pipeline_version,
            "audio_key": existing["output_key"],
            "audio_checksum": existing["output_checksum"],
        }

    try:
        work_dir = workspace(asset_info.asset_id)
        normalized_video = work_dir / "normalized.mp4"
        if not normalized_video.exists():
            # Correction 1 : appel avec un seul argument object_key (bucket par défaut)
            download_file(
                f"media-derived/{asset_info.asset_id}/normalized/video.mp4",
                normalized_video,
            )

        audio_result = extract_audio_file(asset_info.asset_id, normalized_video, work_dir)

        finish_step(operation_key, audio_result["checksum"], audio_result["object_key"])

        update_asset_state(asset_info.asset_id, ProcessingEvent.AUDIO_OK, progress=90)

        activity.logger.info(f"Audio extraction successful for asset {asset_info.asset_id}")
        return {
            "asset_id": asset_info.asset_id,
            "pipeline_version": asset_info.pipeline_version,
            "audio_key": audio_result["object_key"],
            "audio_checksum": audio_result["checksum"],
        }

    except Exception as exc:
        activity.logger.error(f"Error in extract_audio for asset {asset_info.asset_id}: {exc}")
        fail_step(operation_key, str(exc))
        update_asset_state(asset_info.asset_id, ProcessingEvent.ERROR, error=str(exc))
        raise
    finally:
        work_dir = workspace(asset_info.asset_id)
        shutil.rmtree(work_dir, ignore_errors=True)


@activity.defn
async def generate_thumbnail(asset_input: dict) -> dict:
    """
    Generate the default thumbnail.
    This activity is idempotent.
    """
    activity.logger.info(f"Starting generate_thumbnail for asset {asset_input['asset_id']}")

    with get_session() as db:
        asset = get_asset_status(db, asset_input["asset_id"])
        if asset is None:
            raise RuntimeError("ASSET_NOT_FOUND")
        asset_info = AssetInfo(
            id=asset.id,
            asset_id=asset.asset_id,
            source_checksum=asset.source_checksum,
            pipeline_version=asset.pipeline_version,
            minio_bucket=asset.minio_bucket,
            minio_object_key=asset.minio_object_key,
        )

    operation_key, existing = begin_step(
        asset_info,
        "thumbnail",
        tool_version="ffmpeg-thumbnail-v1",
    )

    if existing:
        activity.logger.info(f"Thumbnail step already completed for asset {asset_info.asset_id}, reusing result")
        update_asset_state(asset_info.asset_id, ProcessingEvent.THUMBNAIL_OK, progress=100)
        return {
            "asset_id": asset_info.asset_id,
            "pipeline_version": asset_info.pipeline_version,
            "thumbnail_key": existing["output_key"],
        }

    try:
        work_dir = workspace(asset_info.asset_id)
        normalized_video = work_dir / "normalized.mp4"
        if not normalized_video.exists():
            # Correction 1 : appel avec un seul argument object_key
            download_file(
                f"media-derived/{asset_info.asset_id}/normalized/video.mp4",
                normalized_video,
            )

        thumbnail_path = work_dir / "thumbnail.jpg"
        generate_thumbnail_file(normalized_video, thumbnail_path)

        checksum = sha256_file(thumbnail_path)
        upload = upload_thumbnail(asset_info.asset_id, thumbnail_path)

        finish_step(operation_key, checksum, upload["object_key"])

        update_asset_state(asset_info.asset_id, ProcessingEvent.THUMBNAIL_OK, progress=100)

        activity.logger.info(f"Thumbnail generation successful for asset {asset_info.asset_id}")
        return {
            "asset_id": asset_info.asset_id,
            "pipeline_version": asset_info.pipeline_version,
            "thumbnail_key": upload["object_key"],
        }

    except Exception as exc:
        activity.logger.error(f"Error in generate_thumbnail for asset {asset_info.asset_id}: {exc}")
        fail_step(operation_key, str(exc))
        update_asset_state(asset_info.asset_id, ProcessingEvent.ERROR, error=str(exc))
        raise
    finally:
        work_dir = workspace(asset_info.asset_id)
        shutil.rmtree(work_dir, ignore_errors=True)