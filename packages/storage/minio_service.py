from pathlib import Path

from minio import Minio
from minio.error import S3Error

from packages.config.settings import settings


client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)


def create_bucket():
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


# ---- Deterministic derived object keys ------------------------------------
def build_proxy_object_key(asset_id: str) -> str:
    return f"media-derived/{asset_id}/proxy/720p.mp4"


def build_audio_object_key(asset_id: str) -> str:
    return f"media-derived/{asset_id}/audio/source.wav"


def build_thumbnail_object_key(asset_id: str) -> str:
    return f"media-derived/{asset_id}/thumbnail/default.jpg"


def build_manifest_object_key(asset_id: str, name: str) -> str:
    return f"media-derived/{asset_id}/manifests/{name}.json"


def object_exists(object_key: str) -> bool:
    """Return True if the object is present. Used to verify a stored artifact
    before marking a step complete, and to confirm a previously completed
    output still exists before reusing it."""
    try:
        client.stat_object(settings.MINIO_BUCKET, object_key)
        return True
    except S3Error as exc:
        if exc.code in ("NoSuchKey", "NoSuchObject", "NotFound"):
            return False
        raise


def build_original_object_key(asset_id: str, extension: str) -> str:
    """Deterministic key for the stored original media."""
    return f"media-original/{asset_id}/original.{extension}"


def upload_original_video(
    asset_id: str,
    file_path: Path,
    extension: str = "mp4",
):
    object_key = build_original_object_key(asset_id, extension)

    result = client.fput_object(
        settings.MINIO_BUCKET,
        object_key,
        str(file_path),
    )

    return {
        "bucket": settings.MINIO_BUCKET,
        "object_key": object_key,
        "etag": result.etag,
        "size": file_path.stat().st_size,
    }


def delete_object(object_key: str) -> None:
    """Remove an object; used to roll back a stored original when a later
    step (e.g. database persistence) fails, so no orphaned objects remain."""
    client.remove_object(settings.MINIO_BUCKET, object_key)


def upload_audio(
    asset_id: str,
    file_path: Path,
):
    object_key = build_audio_object_key(asset_id)

    result = client.fput_object(
        settings.MINIO_BUCKET,
        object_key,
        str(file_path),
    )

    return {
        "bucket": settings.MINIO_BUCKET,
        "object_key": object_key,
        "etag": result.etag,
        "size": file_path.stat().st_size,
    }


def upload_thumbnail(
    asset_id: str,
    file_path: Path,
):
    object_key = build_thumbnail_object_key(asset_id)

    result = client.fput_object(
        settings.MINIO_BUCKET,
        object_key,
        str(file_path),
    )

    return {
        "bucket": settings.MINIO_BUCKET,
        "object_key": object_key,
        "etag": result.etag,
        "size": file_path.stat().st_size,
    }


def download_file(
    object_key: str,
    destination: Path,
):
    client.fget_object(
        settings.MINIO_BUCKET,
        object_key,
        str(destination),
    )

    return destination


def get_object(object_key: str):
    return client.get_object(
        settings.MINIO_BUCKET,
        object_key,
    )


def upload_json_manifest(asset_id: str, name: str, file_path: Path):
    object_key = build_manifest_object_key(asset_id, name)

    result = client.fput_object(
        settings.MINIO_BUCKET,
        object_key,
        str(file_path),
        content_type="application/json",
    )

    return {
        "bucket": settings.MINIO_BUCKET,
        "object_key": object_key,
        "etag": result.etag,
        "size": file_path.stat().st_size,
    }


def upload_normalized_video(
    asset_id: str,
    file_path: Path,
):
    object_key = build_proxy_object_key(asset_id)

    result = client.fput_object(
        settings.MINIO_BUCKET,
        object_key,
        str(file_path),
    )

    return {
        "bucket": settings.MINIO_BUCKET,
        "object_key": object_key,
        "etag": result.etag,
        "size": file_path.stat().st_size,
    }
