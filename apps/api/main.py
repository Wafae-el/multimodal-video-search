from pathlib import Path
import shutil

from fastapi import FastAPI, UploadFile, File, Depends
from sqlalchemy.orm import Session

from temporalio.client import Client

from packages.metadata.database import get_db
from packages.metadata.crud import create_video
from packages.media.ffprobe_service import analyze_video
from packages.storage.minio_service import upload_video as upload_to_minio
from packages.workflow.workflows import ProcessAssetWorkflow

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
    # Sauvegarder la vidéo temporairement
    file_path = TEMP_DIR / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Analyse FFprobe
    try:
        metadata = analyze_video(file_path)
    except Exception as e:
        return {
        "status": "FAILED",
        "error": str(e),
        }

    video_stream = next(
        stream
        for stream in metadata["streams"]
        if stream["codec_type"] == "video"
    )
    audio_stream = next(
        (
            stream
            for stream in metadata["streams"]
            if stream["codec_type"] == "audio"
        ),
        None,
    )
    
    if audio_stream is None:
        return {
            "status": "NO_AUDIO",
            "error": "No audio stream found",
        }

    # Sauvegarde des métadonnées

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

    # Upload vers MinIO
    upload_to_minio(file_path)

    # Démarrage du Workflow Temporal
    client = await Client.connect("localhost:7233")

    await client.start_workflow(
    ProcessAssetWorkflow.run,
    {
        "video_id": video.id,
        "filename": file.filename,
        "pipeline_version": "v1",
    },
    id=f"process-video-{video.id}",
    task_queue="video-processing",
    )

    return {
        "message": "Video uploaded successfully",
        "video_id": video.id,
        "workflow": "started",
        "metadata": metadata,
    }