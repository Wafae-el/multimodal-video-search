import hashlib
import shutil
import uuid
from pathlib import Path

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session
from temporalio.client import Client

from packages.config.settings import settings
from packages.metadata.database import get_db
from packages.metadata.crud import (
    create_asset,
    register_original_media,
    get_asset_status,
)
from packages.media.ffprobe_service import (
    analyze_video,
    MediaValidationError,
)
from packages.storage.minio_service import (
    upload_original_video,
    create_bucket,
)
from packages.workflow.workflows import (
    ProcessAssetWorkflow,
    WorkflowInput,
)
from packages.workflow.state_machine import ProcessingState  # <-- Import ajouté

app = FastAPI(
    title="Multimodal Video Search API",
    version="1.0.0",
)

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Modèles ----------
class UploadResponse(BaseModel):
    asset_id: str
    workflow_id: str
    status: str

class ErrorResponse(BaseModel):
    error: str
    code: str

class AssetStatusResponse(BaseModel):
    asset_id: str
    status: str
    progress: int
    attempts: int
    last_error: str | None = None

# ---------- Constantes ----------
# Utilisation de la liste définie dans settings
ALLOWED_TYPES = {
    t.strip()
    for t in settings.ALLOWED_CONTENT_TYPES.split(",")
}
MAX_SIZE = settings.MAX_UPLOAD_SIZE

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            digest.update(chunk)
    return digest.hexdigest()

# ---------- Événements ----------
@app.on_event("startup")
async def startup():
    create_bucket()

# ---------- Routes ----------
@app.get("/")
def root():
    return {"status": "running"}

@app.post(
    "/v1/upload",
    response_model=UploadResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
    },
)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    asset_id = str(uuid.uuid4())

    # Vérification du type MIME
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "UNSUPPORTED_MEDIA_TYPE",
                "error": "Unsupported media type",
            },
        )

    safe_name = Path(file.filename).name
    temp_file = TEMP_DIR / f"{asset_id}.upload"

    try:
        # Sauvegarde temporaire
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = temp_file.stat().st_size
        if file_size > MAX_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "code": "FILE_TOO_LARGE",
                    "error": "Upload exceeds maximum size",
                },
            )

        checksum = sha256_file(temp_file)

        # Analyse avec ffprobe
        try:
            metadata = analyze_video(temp_file)
        except MediaValidationError as exc:
            code_map = {
                "CORRUPT_MEDIA": status.HTTP_400_BAD_REQUEST,
                "UNSUPPORTED_MEDIA": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "MISSING_VIDEO_STREAM": status.HTTP_400_BAD_REQUEST,
                "FFPROBE_TIMEOUT": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "FFPROBE_UNAVAILABLE": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            raise HTTPException(
                status_code=code_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
                detail={"code": exc.code, "error": exc.code},
            )

        if not metadata.has_audio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "NO_AUDIO",
                    "error": "Video has no audio stream",
                },
            )

        # Upload vers MinIO
        upload = upload_original_video(asset_id, temp_file)

        # Création de l'asset en base
        asset = create_asset(
            db=db,
            asset_id=asset_id,
            filename=safe_name,
            content_type=file.content_type,
            duration=metadata.duration,
            duration_ms=int(metadata.duration * 1000),
            codec=metadata.video_codec,
            width=metadata.width,
            height=metadata.height,
            size=file_size,
            source_checksum=checksum,
            pipeline_version=settings.PIPELINE_VERSION,
            minio_bucket=upload["bucket"],
            minio_object_key=upload["object_key"],
            status=ProcessingState.UPLOADED.value,   # <-- Utilisation de l'enum
            progress=0,
        )

        # Enregistrement du média original
        register_original_media(
            db=db,
            video_id=asset.id,
            bucket=upload["bucket"],
            object_key=upload["object_key"],
            checksum=checksum,
        )

        # Connexion à Temporal et démarrage du workflow
        client = await Client.connect(settings.TEMPORAL_ADDRESS)
        workflow_id = f"asset-{asset.asset_id}"
        await client.start_workflow(
            ProcessAssetWorkflow.run,
            WorkflowInput(
                asset_id=asset.asset_id,
                pipeline_version=asset.pipeline_version,
            ),
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )

        # Mise à jour du workflow_id dans l'asset
        asset.workflow_id = workflow_id
        db.commit()

        return UploadResponse(
            asset_id=asset.asset_id,
            workflow_id=workflow_id,
            status="UPLOADED",
        )

    finally:
        # Nettoyage du fichier temporaire
        if temp_file.exists():
            temp_file.unlink()


@app.get(
    "/v1/assets/{asset_id}",
    response_model=AssetStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
def asset_status(
    asset_id: str,
    db: Session = Depends(get_db),
):
    asset = get_asset_status(db, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ASSET_NOT_FOUND",
                "error": "Asset not found",
            },
        )
    return AssetStatusResponse(
        asset_id=asset.asset_id,
        status=asset.status,
        progress=asset.progress,
        attempts=asset.attempts,
        last_error=asset.last_error,
    )