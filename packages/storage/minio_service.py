from minio import Minio
from pathlib import Path
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "admin12345"
BUCKET_NAME = "videos"
client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)
def create_bucket():
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
def upload_video(file_path: Path):
    create_bucket()

    client.fput_object(
        BUCKET_NAME,
        file_path.name,
        str(file_path),
    )