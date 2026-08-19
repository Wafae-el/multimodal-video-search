import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session
from temporalio.client import Client

from packages.config.settings import settings
from packages.metadata.database import get_db
from packages.metadata.crud import (
    create_pending_asset,
    mark_asset_failed,
    finalize_original_upload,
    set_asset_error,
    get_asset_status,
    get_processing_steps,
)
from packages.media.ffprobe_service import analyze_video, MediaValidationError
from packages.storage.minio_service import (
    build_original_object_key,
    upload_original_video,
    delete_object,
    create_bucket,
)
from packages.workflow.workflows import ProcessAssetWorkflow
from packages.workflow.contracts import ProcessAssetInput
from packages.workflow.state_machine import ProcessingState
from packages.audio_quality.quality import renormalize_active_weights

logger = logging.getLogger("api.upload")

app = FastAPI(
    title="Multimodal Video Search API",
    version="1.0.0",
)

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 1024 * 1024


# ---------- Response models ----------
class UploadResponse(BaseModel):
    asset_id: str
    workflow_id: str
    status: str


class ErrorResponse(BaseModel):
    error: str
    code: str
    # Present when a durable asset record was created (invalid / no-audio media),
    # so the client can poll GET /v1/assets/{asset_id}.
    asset_id: str | None = None


class StepStatus(BaseModel):
    step_name: str
    state: str
    attempts: int


class QueryMediaRef(BaseModel):
    media_id: str
    media_type: str


class SearchRequest(BaseModel):
    text: str | None = None
    query_media_ids: list[QueryMediaRef] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=lambda: ["transcript", "visual", "audio"])
    weights: dict[str, float] = Field(
        default_factory=lambda: {"transcript": 0.4, "visual": 0.4, "audio": 0.2}
    )
    filters: dict[str, list[str] | str | int | float] = Field(default_factory=dict)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("modalities")
    @classmethod
    def validate_modalities(cls, value: list[str]) -> list[str]:
        allowed = {"transcript", "visual", "audio"}
        unsupported = sorted(set(value) - allowed)
        if unsupported:
            raise ValueError(f"unsupported modalities: {unsupported}")
        if not value:
            raise ValueError("at least one modality is required")
        return value

    @model_validator(mode="after")
    def validate_query_and_weights(self) -> "SearchRequest":
        if not self.text and not self.query_media_ids:
            raise ValueError("text or query_media_ids is required")
        if any(weight < 0 for weight in self.weights.values()):
            raise ValueError("weights must be non-negative")
        renormalize_active_weights(self.weights, set(self.modalities))
        return self


class ChannelContribution(BaseModel):
    modality: str
    score: float


class SearchResult(BaseModel):
    asset_id: str
    start_ms: int
    end_ms: int
    final_score: float
    transcript: str | None = None
    preview_url: str | None = None
    channels: list[ChannelContribution] = Field(default_factory=list)
    evidence: list[dict[str, str]] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query_id: str
    results: list[SearchResult]
    diagnostics: dict[str, str | int | float | dict[str, float]] = Field(default_factory=dict)


_SEARCH_CACHE: dict[str, SearchResponse] = {}


class AssetStatusResponse(BaseModel):
    asset_id: str
    status: str
    progress: int
    # Asset-level attempts = the maximum attempt count across processing steps
    # (1 on a clean run; increases when any step is retried).
    attempts: int
    last_error: str | None = None
    steps: list[StepStatus] = []


# ---------- Structured error handling ----------
class APIError(Exception):
    """Carries a stable error code, HTTP status and safe message. Raw internal
    exception strings are never propagated to the client."""

    def __init__(self, status_code: int, code: str, message: str, asset_id: str | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.asset_id = asset_id
        super().__init__(message)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.message,
            code=exc.code,
            asset_id=exc.asset_id,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    # Log the real cause server-side; return a stable, non-leaking body.
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error="Internal server error", code="INTERNAL_ERROR").model_dump(),
    )


# ---------- Validation configuration ----------
ALLOWED_TYPES = {t.strip() for t in settings.ALLOWED_CONTENT_TYPES.split(",") if t.strip()}
ALLOWED_EXTENSIONS = {
    e.strip().lower() for e in settings.ALLOWED_EXTENSIONS.split(",") if e.strip()
}
MAX_SIZE = settings.MAX_UPLOAD_SIZE
MAX_DURATION = settings.MAX_DURATION_SECONDS

# Maps ffprobe service codes -> (stable API code, HTTP status).
MEDIA_ERROR_MAP = {
    "CORRUPT_MEDIA": ("MEDIA_CORRUPT", 400),
    "UNSUPPORTED_MEDIA": ("MEDIA_UNSUPPORTED", 415),
    "MISSING_VIDEO_STREAM": ("MEDIA_NO_VIDEO_STREAM", 422),
    "FFPROBE_TIMEOUT": ("FFPROBE_TIMEOUT", 503),
    "FFPROBE_UNAVAILABLE": ("FFPROBE_UNAVAILABLE", 503),
}


def sanitize_filename(raw: str | None) -> str:
    """Return a display-safe base name. The filename is never used as identity."""
    if not raw:
        return "upload"
    return Path(raw).name or "upload"


def extract_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


# ---------- Lifecycle ----------
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
    status_code=202,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # 1. Identity is generated before any external write; the filename is never
    #    used as durable identity.
    asset_id = str(uuid.uuid4())
    pipeline_version = settings.PIPELINE_VERSION
    safe_name = sanitize_filename(file.filename)
    extension = extract_extension(safe_name)

    # 2. Request-level validation (MIME + extension) before we persist anything.
    if file.content_type not in ALLOWED_TYPES:
        raise APIError(415, "MEDIA_UNSUPPORTED", "Unsupported media type")
    if extension not in ALLOWED_EXTENSIONS:
        raise APIError(415, "MEDIA_UNSUPPORTED", "Unsupported file extension")

    temp_file = TEMP_DIR / f"{asset_id}.upload"

    try:
        # 3. Stream to disk, computing the checksum and size in one pass and
        #    enforcing the size limit while streaming.
        digest = hashlib.sha256()
        size = 0
        with open(temp_file, "wb") as buffer:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_SIZE:
                    raise APIError(413, "MEDIA_TOO_LARGE", "Upload exceeds maximum size")
                digest.update(chunk)
                buffer.write(chunk)
        checksum = digest.hexdigest()

        # 4. Create the durable validation record BEFORE completing validation,
        #    so invalid / no-audio outcomes remain observable via GET.
        create_pending_asset(
            db=db,
            asset_id=asset_id,
            filename=safe_name,
            content_type=file.content_type,
            source_checksum=checksum,
            size=size,
            pipeline_version=pipeline_version,
            status=ProcessingState.VALIDATING.value,
        )

        # 5. Media validation via ffprobe. Failures are persisted as FAILED.
        try:
            metadata = analyze_video(temp_file)
        except MediaValidationError as exc:
            api_code, http_status = MEDIA_ERROR_MAP.get(exc.code, ("MEDIA_CORRUPT", 400))
            mark_asset_failed(
                db,
                asset_id,
                status=ProcessingState.FAILED.value,
                error_code=api_code,
                progress=0,
            )
            raise APIError(http_status, api_code, "Media validation failed", asset_id=asset_id)

        # 6. Optional duration limit.
        if MAX_DURATION is not None and metadata.duration > MAX_DURATION:
            mark_asset_failed(
                db,
                asset_id,
                status=ProcessingState.FAILED.value,
                error_code="MEDIA_DURATION_EXCEEDED",
                progress=0,
            )
            raise APIError(
                422, "MEDIA_DURATION_EXCEEDED", "Media duration exceeds limit", asset_id=asset_id
            )

        # 7. Valid video without audio: persist NO_AUDIO explicitly and stop.
        #    NO_AUDIO is a terminal Week 1 state (no workflow is started).
        if not metadata.has_audio:
            mark_asset_failed(
                db,
                asset_id,
                status=ProcessingState.NO_AUDIO.value,
                error_code="MEDIA_NO_AUDIO",
                progress=0,
            )
            raise APIError(422, "MEDIA_NO_AUDIO", "Video has no audio stream", asset_id=asset_id)

        # 8. Store the original at a deterministic key. A per-asset key means a
        #    retry for a different asset can never overwrite another asset.
        object_key = build_original_object_key(asset_id, extension or "mp4")
        try:
            upload = upload_original_video(asset_id, temp_file, extension or "mp4")
        except Exception:
            logger.exception("MinIO upload failed for asset %s", asset_id)
            mark_asset_failed(
                db,
                asset_id,
                status=ProcessingState.FAILED.value,
                error_code="STORAGE_ERROR",
                progress=0,
            )
            raise APIError(503, "STORAGE_ERROR", "Failed to store media", asset_id=asset_id)

        # 9. Deterministic workflow id, persisted atomically with the media_file
        #    row (asset update + media_file insert in one transaction). If this
        #    fails after the object is stored, delete the object (no orphans).
        workflow_id = f"process-asset-{asset_id}-{pipeline_version}"
        try:
            finalize_original_upload(
                db,
                asset_id,
                bucket=upload["bucket"],
                object_key=object_key,
                duration=metadata.duration,
                duration_ms=int(metadata.duration * 1000),
                codec=metadata.video_codec,
                width=metadata.width,
                height=metadata.height,
                workflow_id=workflow_id,
                status=ProcessingState.UPLOADED.value,
            )
        except Exception:
            logger.exception("DB finalize failed for asset %s; rolling back object", asset_id)
            try:
                delete_object(object_key)
            except Exception:
                logger.exception("Failed to delete orphaned object %s", object_key)
            mark_asset_failed(
                db,
                asset_id,
                status=ProcessingState.FAILED.value,
                error_code="DB_PERSIST_FAILED",
                progress=0,
            )
            raise APIError(
                500, "DB_PERSIST_FAILED", "Failed to persist media record", asset_id=asset_id
            )

        # 10. Dispatch the durable workflow. The workflow id is already persisted,
        #     so if dispatch fails the asset stays in a recoverable UPLOADED state
        #     with last_error set, and a retry can safely re-dispatch the same id.
        try:
            client = await Client.connect(settings.TEMPORAL_ADDRESS)
            await client.start_workflow(
                ProcessAssetWorkflow.run,
                ProcessAssetInput(asset_id=asset_id, pipeline_version=pipeline_version),
                id=workflow_id,
                task_queue=settings.TEMPORAL_TASK_QUEUE,
            )
        except Exception:
            logger.exception("Workflow dispatch failed for asset %s", asset_id)
            set_asset_error(db, asset_id, error_code="WORKFLOW_DISPATCH_FAILED")
            raise APIError(
                500,
                "WORKFLOW_DISPATCH_FAILED",
                "Media stored but processing could not be started; retry is safe",
                asset_id=asset_id,
            )

        return UploadResponse(
            asset_id=asset_id,
            workflow_id=workflow_id,
            status=ProcessingState.UPLOADED.value,
        )

    finally:
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
        raise APIError(404, "ASSET_NOT_FOUND", "Asset not found")
    steps = [
        StepStatus(step_name=s.step_name, state=s.state, attempts=s.attempts or 0)
        for s in get_processing_steps(db, asset_id)
    ]
    return AssetStatusResponse(
        asset_id=asset.asset_id,
        status=asset.status,
        progress=asset.progress,
        attempts=asset.attempts or 0,
        last_error=asset.last_error,
        steps=steps,
    )


@app.post(
    "/v1/search",
    response_model=SearchResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def search(request: SearchRequest):
    """Stable Week 7 search contract.

    The model-serving and Qdrant retrieval backends are intentionally not hidden
    here. Until those deploy, the route validates the contract, normalizes active
    weights, returns an empty ranked list and exposes diagnostics for client tests.
    """
    try:
        normalized = renormalize_active_weights(request.weights, set(request.modalities))
    except ValueError as exc:
        raise APIError(422, "INVALID_WEIGHTS", str(exc))

    query_id = str(uuid.uuid4())
    response = SearchResponse(
        query_id=query_id,
        results=[],
        diagnostics={
            "status": "NO_INDEX_READY",
            "modalities": len(request.modalities),
            "weights": normalized,
        },
    )
    _SEARCH_CACHE[query_id] = response
    return response


@app.get(
    "/v1/search/{query_id}",
    response_model=SearchResponse,
    responses={404: {"model": ErrorResponse}},
)
def search_status(query_id: str):
    response = _SEARCH_CACHE.get(query_id)
    if response is None:
        raise APIError(404, "QUERY_NOT_FOUND", "Query not found")
    return response


@app.post("/v1/reindex/{asset_id}", responses={404: {"model": ErrorResponse}})
def reindex_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = get_asset_status(db, asset_id)
    if asset is None:
        raise APIError(404, "ASSET_NOT_FOUND", "Asset not found")
    return {"asset_id": asset_id, "status": "REINDEX_QUEUED"}


@app.delete("/v1/assets/{asset_id}", responses={404: {"model": ErrorResponse}})
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = get_asset_status(db, asset_id)
    if asset is None:
        raise APIError(404, "ASSET_NOT_FOUND", "Asset not found")
    return {"asset_id": asset_id, "status": "DELETE_ACCEPTED"}
