from pathlib import Path
import shutil

from fastapi import FastAPI, UploadFile, File, Depends
from sqlalchemy.orm import Session

from packages.metadata.database import get_db
from packages.metadata.crud import create_video
from packages.media.ffprobe_service import analyze_video
from packages.storage.minio_service import upload_video as upload_to_minio

app = FastAPI(
    title="Multimodal Video Search API",
    version="0.1.0",
)

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)


@app.get("/")
def root():
    return {"status": "running"}


@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    file_path = TEMP_DIR / file.filename

    # Sauvegarder la vidéo
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Analyser la vidéo
    metadata = analyze_video(file_path)

    video_stream = next(
        stream
        for stream in metadata["streams"]
        if stream["codec_type"] == "video"
    )

    # Enregistrer les métadonnées dans PostgreSQL
    create_video(
        db=db,
        filename=file.filename,
        content_type=file.content_type,
        duration=float(metadata["format"]["duration"]),
        codec=video_stream["codec_name"],
        width=video_stream["width"],
        height=video_stream["height"],
        size=int(metadata["format"]["size"]),
    )

    # Envoyer la vidéo dans MinIO
    upload_to_minio(file_path)

    return metadata
@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    print("1. Upload started")

    file_path = TEMP_DIR / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print("2. File saved")

    metadata = analyze_video(file_path)
    print("3. ffprobe OK")

    video_stream = next(
        stream
        for stream in metadata["streams"]
        if stream["codec_type"] == "video"
    )

    print("4. About to insert into PostgreSQL")

    video = create_video(
        db=db,
        filename=file.filename,
        content_type=file.content_type,
        duration=float(metadata["format"]["duration"]),
        codec=video_stream["codec_name"],
        width=video_stream["width"],
        height=video_stream["height"],
        size=int(metadata["format"]["size"]),
    )

    print("5. PostgreSQL OK:", video.id)

    upload_to_minio(file_path)

    print("6. MinIO OK")

    return metadata