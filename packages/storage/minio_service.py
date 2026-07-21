from pathlib import Path

from minio import Minio

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


def upload_original_video(
    asset_id: str,
    file_path: Path,
):
    object_key = f"media-original/{asset_id}/original.mp4"

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


def upload_audio(
    asset_id: str,
    file_path: Path,
):
    object_key = f"media-derived/{asset_id}/audio/source.wav"

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
    object_key = (
        f"media-derived/{asset_id}/thumbnail/default.jpg"
    )

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
def upload_normalized_video(
    asset_id: str,
    file_path: Path,
):
    object_key = (
        f"media-derived/{asset_id}/normalized/video.mp4"
    )

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