import hashlib
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError

from packages.metadata.database import get_session
from packages.metadata import crud
from packages.media.ffprobe_service import (
    analyze_video,
    MediaValidationError,
    verify_video_output,
    verify_audio_output,
)
from packages.media.normalizer import normalize_video as normalize_video_file
from packages.media.thumbnail_service import generate_thumbnail as generate_thumbnail_file
from packages.segmentation.audio_extractor import extract_audio as extract_audio_file
from packages.storage.minio_service import (
    download_file,
    upload_thumbnail,
    upload_normalized_video,
    object_exists,
    build_proxy_object_key,
)
from packages.workflow.state_machine import ProcessingState
from packages.workflow.operation_key import build_operation_key  # re-exported for callers/tests
from packages.workflow.contracts import ProcessAssetInput, ACTIVITY_MAX_ATTEMPTS


WORKSPACE_ROOT = Path("workspace")
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


@dataclass
class AssetInfo:
    """Only the data an activity needs — no binary payloads or blobs."""
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


def workspace(asset_id: str, operation_key: str) -> Path:
    """One isolated workspace per asset AND operation key, so concurrent or
    retried steps never collide."""
    path = WORKSPACE_ROOT / asset_id / operation_key[:16]
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log_context(asset_id: str, step_name: str, operation_key: str) -> dict:
    """Structured log fields: asset_id, workflow_id, activity, operation_key, attempt."""
    workflow_id = None
    attempt = None
    try:
        info = activity.info()
        workflow_id = info.workflow_id
        attempt = info.attempt
    except Exception:  # not in an activity context (should not happen in prod)
        pass
    return {
        "asset_id": asset_id,
        "workflow_id": workflow_id,
        "activity": step_name,
        "operation_key": operation_key,
        "attempt": attempt,
    }


def _load_asset_info(asset_id: str) -> AssetInfo:
    with get_session() as db:
        asset = crud.get_asset_status(db, asset_id)
        if asset is None:
            raise ApplicationError("ASSET_NOT_FOUND", type="AssetNotFound", non_retryable=True)
        return AssetInfo(
            id=asset.id,
            asset_id=asset.asset_id,
            source_checksum=asset.source_checksum,
            pipeline_version=asset.pipeline_version,
            minio_bucket=asset.minio_bucket,
            minio_object_key=asset.minio_object_key,
        )


def download_original_video(info: AssetInfo, workdir: Path) -> Path:
    local = workdir / "original"
    download_file(info.minio_object_key, local)
    return local


def _ensure_proxy(info: AssetInfo, workdir: Path) -> Path:
    proxy = workdir / "proxy.mp4"
    if not proxy.exists():
        download_file(build_proxy_object_key(info.asset_id), proxy)
    return proxy


def _result(asset_id: str, pipeline_version: str, data: dict, reused: bool) -> dict:
    # Only stable strings are returned into Temporal history.
    return {
        "asset_id": asset_id,
        "pipeline_version": pipeline_version,
        "output_key": data.get("output_key"),
        "output_checksum": data.get("output_checksum"),
        "reused": reused,
    }


def _run_step(
    request: ProcessAssetInput,
    *,
    step_name: str,
    tool_version: str,
    start_states,
    done_state: ProcessingState,
    done_progress,
    work,
) -> dict:
    """Shared retry-safe, idempotent scaffolding for every activity.

    Flow: load asset -> idempotently enter the step's state(s) -> compute the
    operation key -> begin/resume/reuse the step -> if already completed and the
    artifact still exists, return it without re-running FFmpeg -> otherwise do the
    work, verify the written object, mark the step complete and advance the asset
    state. Failures are retryable by default; terminal FAILED is written only for
    non-retryable errors or once retries are exhausted.
    """
    asset_id = request.asset_id
    info = _load_asset_info(asset_id)

    operation_key = build_operation_key(
        info.source_checksum, step_name, info.pipeline_version, tool_version
    )
    ctx = _log_context(asset_id, step_name, operation_key)

    # Enter this step's in-progress state(s). Monotonic + idempotent, so a retry
    # that finds the asset already advanced does not raise an invalid transition.
    with get_session() as db:
        for state in start_states:
            crud.advance_asset_state(db, asset_id, target=state)

    with get_session() as db:
        step = crud.begin_or_resume_step(
            db,
            video_id=info.id,
            step_name=step_name,
            step_version=info.pipeline_version,
            tool_version=tool_version,
            input_checksum=info.source_checksum,
            operation_key=operation_key,
        )

    # Duplicate delivery / output-exists: a completed step whose artifact still
    # exists is reused as-is — FFmpeg is never invoked again and the attempt count
    # is not increased.
    if step["status"] == "completed":
        if not step["output_key"] or object_exists(step["output_key"]):
            with get_session() as db:
                crud.advance_asset_state(db, asset_id, target=done_state, progress=done_progress)
            activity.logger.info(
                "reusing completed output asset=%s op=%s", asset_id, operation_key, extra=ctx
            )
            return _result(asset_id, info.pipeline_version, step, reused=True)
        activity.logger.warning(
            "completed output missing; recomputing asset=%s op=%s", asset_id, operation_key, extra=ctx
        )

    # A "run" outcome bumped attempts; keep logs in sync with the actual attempt.
    activity.logger.info(
        "activity execution begin asset=%s op=%s", asset_id, operation_key, extra=ctx
    )

    # Heartbeat from a background thread while the blocking work runs, so if the
    # worker is killed mid-activity Temporal detects it within heartbeat_timeout
    # and reschedules the (idempotent) activity instead of waiting for
    # start_to_close_timeout.
    stop_heartbeat = threading.Event()

    def _heartbeat_loop():
        while not stop_heartbeat.wait(2.0):
            try:
                activity.heartbeat()
            except Exception:
                return

    heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    heartbeat_thread.start()

    workdir = workspace(asset_id, operation_key)
    try:
        result = work(info, workdir)

        # Verify the written object exists before marking the step complete.
        if result.get("output_key") and not object_exists(result["output_key"]):
            raise RuntimeError("OUTPUT_VERIFICATION_FAILED")

        with get_session() as db:
            crud.complete_step(
                db, operation_key,
                output_bucket=result.get("output_bucket"),
                output_key=result.get("output_key"),
                output_checksum=result.get("output_checksum"),
            )
            # Persist a media_files record for a produced artifact (idempotent).
            if result.get("file_type") and result.get("output_key"):
                crud.register_media_file(
                    db,
                    video_id=info.id,
                    file_type=result["file_type"],
                    bucket=result.get("output_bucket"),
                    object_key=result["output_key"],
                    checksum=result.get("output_checksum"),
                )
            crud.advance_asset_state(db, asset_id, target=done_state, progress=done_progress)

        activity.logger.info(
            "activity completed asset=%s op=%s", asset_id, operation_key, extra=ctx
        )
        return _result(asset_id, info.pipeline_version, result, reused=False)

    except MediaValidationError as exc:
        # Bad media never succeeds on retry -> non-retryable, terminal FAILED.
        with get_session() as db:
            crud.fail_step(db, operation_key, error=exc.code)
            crud.mark_asset_failed(
                db, asset_id, status=ProcessingState.FAILED.value, error_code=exc.code
            )
        activity.logger.warning(
            "activity failed (non-retryable) asset=%s op=%s: %s",
            asset_id, operation_key, exc.code, extra=ctx,
        )
        raise ApplicationError(exc.code, type="MediaValidationError", non_retryable=True)

    except Exception as exc:
        message = f"{step_name}:{type(exc).__name__}:{str(exc)[:300]}"
        last_attempt = activity.info().attempt >= ACTIVITY_MAX_ATTEMPTS
        with get_session() as db:
            crud.fail_step(db, operation_key, error=message)
            if last_attempt:
                # Retries exhausted -> terminal failure.
                crud.mark_asset_failed(
                    db, asset_id, status=ProcessingState.FAILED.value, error_code=message
                )
            else:
                # Retryable: keep the current state and let Temporal retry.
                crud.set_asset_error(db, asset_id, error_code=message)
        activity.logger.warning(
            "activity failed asset=%s op=%s last_attempt=%s: %s",
            asset_id, operation_key, last_attempt, message, extra=ctx,
        )
        raise
    finally:
        stop_heartbeat.set()
        shutil.rmtree(workdir, ignore_errors=True)


# ---------- Work functions (the actual FFmpeg / ffprobe steps) ----------
def _probe_json(metadata) -> str:
    return (
        "{\n"
        f'  "duration": {metadata.duration},\n'
        f'  "codec": "{metadata.video_codec}",\n'
        f'  "width": {metadata.width},\n'
        f'  "height": {metadata.height},\n'
        f'  "has_audio": {str(metadata.has_audio).lower()}\n'
        "}"
    )


def _do_probe(info: AssetInfo, workdir: Path) -> dict:
    local_video = download_original_video(info, workdir)
    metadata = analyze_video(local_video)  # validates JSON + video stream
    probe_file = workdir / "probe.json"
    probe_file.write_text(_probe_json(metadata))
    return {
        "output_bucket": None,
        "output_key": None,
        "output_checksum": sha256_file(probe_file),
        "file_type": None,
    }


def _do_normalize(info: AssetInfo, workdir: Path) -> dict:
    local_video = download_original_video(info, workdir)
    proxy = workdir / "proxy.mp4"
    normalize_video_file(local_video, proxy)
    verify_video_output(proxy)  # ffprobe: the proxy is a real decodable video
    checksum = sha256_file(proxy)
    upload = upload_normalized_video(info.asset_id, proxy)
    return {
        "output_bucket": upload["bucket"],
        "output_key": upload["object_key"],
        "output_checksum": checksum,
        "file_type": "proxy",
    }


def _do_extract_audio(info: AssetInfo, workdir: Path) -> dict:
    proxy = _ensure_proxy(info, workdir)
    audio = extract_audio_file(info.asset_id, proxy, workdir)
    verify_audio_output(audio["path"])  # ffprobe: PCM s16le / 16 kHz / mono
    return {
        "output_bucket": audio.get("bucket"),
        "output_key": audio["object_key"],
        "output_checksum": audio["checksum"],
        "file_type": "audio",
    }


def _do_thumbnail(info: AssetInfo, workdir: Path) -> dict:
    proxy = _ensure_proxy(info, workdir)
    thumbnail = workdir / "thumbnail.jpg"
    generate_thumbnail_file(proxy, thumbnail)  # raises if missing/empty
    checksum = sha256_file(thumbnail)
    upload = upload_thumbnail(info.asset_id, thumbnail)
    return {
        "output_bucket": upload["bucket"],
        "output_key": upload["object_key"],
        "output_checksum": checksum,
        "file_type": "thumbnail",
    }


# ---------- Activities ----------
# Synchronous activities: the blocking FFmpeg/ffprobe/MinIO work runs on the
# worker's thread-pool executor (configured in workers/ingestion/worker.py), so
# a long job never blocks the Temporal event loop.
@activity.defn
def probe_video(request: ProcessAssetInput) -> dict:
    return _run_step(
        request,
        step_name="probe",
        tool_version="ffprobe-1",
        start_states=[ProcessingState.VALIDATING, ProcessingState.PROBING],
        done_state=ProcessingState.NORMALIZING,
        done_progress=None,
        work=_do_probe,
    )


@activity.defn
def normalize_video(request: ProcessAssetInput) -> dict:
    return _run_step(
        request,
        step_name="normalize",
        tool_version="ffmpeg-normalizer-v1",
        start_states=[ProcessingState.NORMALIZING],
        done_state=ProcessingState.EXTRACTING_AUDIO,
        done_progress=50,
        work=_do_normalize,
    )


@activity.defn
def extract_audio(request: ProcessAssetInput) -> dict:
    return _run_step(
        request,
        step_name="extract_audio",
        tool_version="ffmpeg-audio-v1",
        start_states=[ProcessingState.EXTRACTING_AUDIO],
        done_state=ProcessingState.GENERATING_THUMBNAIL,
        done_progress=90,
        work=_do_extract_audio,
    )


@activity.defn
def generate_thumbnail(request: ProcessAssetInput) -> dict:
    return _run_step(
        request,
        step_name="thumbnail",
        tool_version="ffmpeg-thumbnail-v1",
        start_states=[ProcessingState.GENERATING_THUMBNAIL],
        done_state=ProcessingState.DONE,
        done_progress=100,
        work=_do_thumbnail,
    )
