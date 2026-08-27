import hashlib
import shutil
import threading
import librosa

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

from packages.media.scene_detector import SceneDetector

from packages.media.frame_selector import FrameSelector
from packages.media.frame_extractor import FrameExtractor
from packages.media.frame_quality import FrameQuality
from packages.media.duplicate_filter import DuplicateFilter

from packages.storage.minio_service import (
    upload_scene_frame,
)

from packages.metadata import crud

from packages.retrieval.service import HybridRetrievalService

from packages.retrieval.visual_qdrant_store import VisualQdrantStore
from packages.visual.openclip_encoder import OpenCLIPVisualEncoder
from packages.storage.minio_service import client
from packages.audio.window_extractor import (
    AudioWindowExtractor,
)
from packages.audio.clap_encoder import (
    CLAPAudioEncoder,
)
from packages.retrieval.audio_qdrant_store import (
    AudioQdrantStore,
)
from packages.audio.quality import AudioQualityAnalyzer
from packages.audio.speech_windows import (
    AudioSpeechWindowAnalyzer,
)

from packages.speech.whisper_service import (
    WhisperService,
)


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
    info.asset_id,
    info.source_checksum,
    step_name,
    info.pipeline_version,
    tool_version,
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
        if step["output_key"] and object_exists(step["output_key"]):
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
def _do_index_audio_windows(
    info: AssetInfo,
    workdir: Path,
) -> dict:

    # ==================================================
    # 1. DOWNLOAD EXTRACTED AUDIO
    # ==================================================

    audio_object_key = (
        f"media-derived/"
        f"{info.asset_id}/"
        f"audio/source.wav"
    )

    local_audio = (
        workdir / "source_audio.wav"
    )

    client.fget_object(
        "media",
        audio_object_key,
        str(local_audio),
    )

    if not local_audio.exists():
        raise FileNotFoundError(local_audio)

    # ==================================================
    # 2. GENERATE 5s WINDOWS / 2.5s OVERLAP
    # ==================================================

    import librosa

    extractor = AudioWindowExtractor(
        window_ms=5000,
        overlap_ms=2500,
    )

    windows_dir = (
        workdir / "audio_windows"
    )

    extracted = extractor.extract(
        local_audio,
        windows_dir,
    )

    if not extracted:
        return {
            "indexed_windows": 0,
            "skipped_silent_windows": 0,
            "asr_segments": 0,
            "collection": "video_audio_windows",
        }

    windows = [
        item[0]
        for item in extracted
    ]

    window_paths = [
        item[1]
        for item in extracted
    ]

    # ==================================================
    # 3. WHISPER ASR
    # ==================================================

    from packages.speech.whisper_service import (
        WhisperService,
    )

    whisper = WhisperService(
        model_size="small",
        device="cpu",
        compute_type="int8",
    )

    segments = whisper.transcribe(
        local_audio
    )

    # ==================================================
    # 4. MAP ASR SEGMENTS TO WINDOWS
    # ==================================================

    from packages.audio.speech_windows import (
        AudioSpeechWindowAnalyzer,
    )

    speech_analyzer = (
        AudioSpeechWindowAnalyzer()
    )

    speech_windows = (
        speech_analyzer.analyze(
            windows,
            segments,
        )
    )

    # ==================================================
    # 5. AUDIO QUALITY
    # ==================================================

    quality_analyzer = AudioQualityAnalyzer()

    retained_windows = []
    retained_paths = []
    retained_quality = []

    skipped_silent = 0

    for window, window_path, speech_window in zip(
        windows,
        window_paths,
        speech_windows,
    ):

        # --------------------------------------------------
        # Skip silent windows
        # --------------------------------------------------

        if speech_window.speech_ratio <= 0.0:
            skipped_silent += 1
            continue

        # --------------------------------------------------
        # Load audio samples
        # --------------------------------------------------

        audio, sampling_rate = librosa.load(
            str(window_path),
            sr=48000,
            mono=True,
        )

        # --------------------------------------------------
        # Compute audio quality
        # --------------------------------------------------

        quality_result = (
            quality_analyzer.analyze(
                audio=audio,
                asr_confidence=(
                    speech_window.asr_confidence
                ),
            )
        )

        # --------------------------------------------------
        # Keep only valid acoustic candidates
        # --------------------------------------------------

        retained_windows.append(window)
        retained_paths.append(window_path)

        retained_quality.append(
            {
                "speech_ratio": float(
                    quality_result.speech_ratio
                ),
                "clipping_ratio": float(
                    quality_result.clipping_ratio
                ),
                "loudness": float(
                    quality_result.loudness
                ),
                "snr_proxy": float(
                    quality_result.snr_proxy
                ),
                "snr_norm": float(
                    quality_result.snr_norm
                ),
                "asr_confidence": float(
                    speech_window.asr_confidence
                ),
                "quality_score": float(
                    quality_result.quality
                ),
            }
        )

    # ==================================================
    # 6. NO ACOUSTIC WINDOWS
    # ==================================================

    if not retained_windows:
        return {
            "indexed_windows": 0,
            "skipped_silent_windows": skipped_silent,
            "asr_segments": len(segments),
            "collection": "video_audio_windows",
        }

    # ==================================================
    # 7. CLAP EMBEDDINGS
    # ==================================================

    encoder = CLAPAudioEncoder(
        device="cpu",
    )

    embeddings = (
        encoder.encode_audio_batch(
            retained_paths
        )
    )

    # ==================================================
    # 8. STORE IN QDRANT
    # ==================================================

    store = AudioQdrantStore(
        url="http://qdrant:6333",
    )

    store.create_collection()

    quality_scores = [
        item["quality_score"]
        for item in retained_quality
    ]

    store.upsert_windows(
        windows=retained_windows,
        embeddings=embeddings,
        video_id=info.id,
        quality_scores=quality_scores,
        quality_metadata=retained_quality,
    )

    # ==================================================
    # 9. RESULT
    # ==================================================

    return {
        "indexed_windows": len(
            retained_windows
        ),
        "skipped_silent_windows": skipped_silent,
        "total_windows": len(windows),
        "asr_segments": len(segments),
        "collection": "video_audio_windows",
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
def index_audio_windows(
    request: ProcessAssetInput,
) -> dict:

    return _run_step(
        request,
        step_name="audio_window_indexing",
        tool_version="clap-audio-v1",
        start_states=[
            ProcessingState.EXTRACTING_AUDIO,
        ],
        done_state=ProcessingState.EXTRACTING_AUDIO,
        done_progress=95,
        work=_do_index_audio_windows,
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


def _do_detect_scenes(info: AssetInfo, workdir: Path) -> dict:
    proxy = _ensure_proxy(info, workdir)

    detector = SceneDetector()
    scenes = detector.detect(proxy)

    with get_session() as db:
        for scene in scenes:
            crud.create_scene(
                db,
                video_id=info.id,
                scene_index=scene.scene_id,
                start_ms=scene.start_ms,
                end_ms=scene.end_ms,
                duration_ms=scene.duration_ms,
            )

    return {
        "output_bucket": None,
        "output_key": None,
        "output_checksum": None,
        "file_type": None,
    }

@activity.defn
def detect_scenes(request: ProcessAssetInput) -> dict:
    return _run_step(
        request,
        step_name="scene_detection",
        tool_version="scenedetect-v1",
        start_states=[ProcessingState.DETECTING_SCENES],
        done_state=ProcessingState.DONE,
        done_progress=100,
        work=_do_detect_scenes,
    )

def _do_generate_scene_frames(
    info: AssetInfo,
    workdir: Path,
) -> dict:

    proxy = _ensure_proxy(info, workdir)

    selector = FrameSelector()
    extractor = FrameExtractor()
    quality = FrameQuality()
    duplicate = DuplicateFilter()

    last_upload = None

    with get_session() as db:

        scenes = crud.get_scenes(
            db,
            video_id=info.id,
        )

        frame_requests = selector.select(scenes)

        previous_frame = None

        for frame in frame_requests:

            output_file = (
                workdir
                / f"scene_{frame.scene_index}.jpg"
            )

            extractor.extract(
                proxy,
                frame.timestamp_ms,
                output_file,
            )

            if quality.is_black(output_file):
                continue
            if quality.is_blurry(output_file):
                continue
            if quality.is_bright(output_file):
                continue
            if not quality.has_sufficient_resolution(output_file):
                continue

            if (
                previous_frame is not None
                and duplicate.are_similar(
                    previous_frame,
                    output_file,
                )
            ):
                continue

            previous_frame = output_file

            upload = upload_scene_frame(
                asset_id=info.asset_id,
                scene_index=frame.scene_index,
                file_path=output_file,
            )

            last_upload = upload

            crud.create_scene_frame(
                db,
                scene_id=frame.scene_id,
                timestamp_ms=frame.timestamp_ms,
                bucket=upload["bucket"],
                object_key=upload["object_key"],
                checksum=upload["etag"],
            )

    return {
        "output_bucket": (
            last_upload["bucket"]
            if last_upload
            else None
        ),
        "output_key": None,
        "output_checksum": None,
        "file_type": "scene_frames",
    }


@activity.defn
def generate_scene_frames(
    request: ProcessAssetInput,
) -> dict:
    return _run_step(
        request,
        step_name="scene_frames",
        tool_version="frame-selection-v1",
        start_states=[ProcessingState.DONE],
        done_state=ProcessingState.DONE,
        done_progress=100,
        work=_do_generate_scene_frames,
    )

@activity.defn
def index_visual_frames(
    request: ProcessAssetInput,
) -> dict:
    """
    Encode generated scene frames with OpenCLIP and
    index their embeddings in the visual Qdrant collection.
    """

    from pathlib import Path
    import tempfile

    encoder = OpenCLIPVisualEncoder(
        model_name="ViT-B-32",
        pretrained="openai",
        device="cpu",
    )

    store = VisualQdrantStore(
        url="http://qdrant:6333",
    )

    store.create_collection()

    indexed = 0

    with get_session() as db:

        video = crud.get_asset_status(
            db,
            request.asset_id,
        )

        if video is None:
            raise ValueError(
                f"Video not found for asset_id={request.asset_id}"
            )

        frames = []

        for scene in video.scenes:
            scene_frames = crud.get_scene_frames(
                db,
                scene.id,
            )

            frames.extend(scene_frames)

        if not frames:
            return {
                "indexed_frames": 0,
                "collection": "video_visual_frames",
            }

        with tempfile.TemporaryDirectory() as temp_dir:

            local_paths = []
            valid_frames = []

            for frame in frames:

                if not frame.object_key:
                    continue

                bucket = frame.bucket or "media"

                local_path = (
                    Path(temp_dir)
                    / f"scene_{frame.scene_id}.jpg"
                )

                client.fget_object(
                    bucket,
                    frame.object_key,
                    str(local_path),
                )

                local_paths.append(local_path)
                valid_frames.append(frame)

            if not local_paths:
                return {
                    "indexed_frames": 0,
                    "collection": "video_visual_frames",
                }

            embeddings = encoder.encode_images(
                local_paths
            )

            class FrameRecord:
                def __init__(self, frame):
                    self.scene_id = frame.scene_id
                    self.timestamp_ms = frame.timestamp_ms
                    self.object_key = frame.object_key

            frame_records = [
                FrameRecord(frame)
                for frame in valid_frames
            ]

            store.upsert_frames(
                frames=frame_records,
                embeddings=embeddings,
                video_id=video.id,
            )

            indexed = len(frame_records)

    return {
        "indexed_frames": indexed,
        "collection": "video_visual_frames",
    }
@activity.defn
def transcribe_audio(asset_id: str) -> dict:
    """
    Transcribe extracted audio with Faster-Whisper,
    normalize the transcript and create searchable chunks.
    """

    from pathlib import Path
    import tempfile

    from packages.metadata.database import SessionLocal
    from packages.metadata.models import Video
    from packages.storage.minio_service import client
    from packages.speech.whisper_service import WhisperService
    from packages.speech.normalizer import TranscriptNormalizer
    from packages.speech.chunker import TranscriptChunker

    with SessionLocal() as db:
        asset = (
            db.query(Video)
            .filter(Video.asset_id == asset_id)
            .first()
        )

        if asset is None:
            raise ValueError(f"Asset not found: {asset_id}")

        if not asset.minio_bucket or not asset.minio_object_key:
            raise ValueError(f"Media object not found for asset: {asset_id}")

        bucket = asset.minio_bucket
        object_key = asset.minio_object_key

    audio_object_key = (
        f"media-derived/{asset_id}/audio/source.wav"
    )

    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False,
    ) as tmp:
        local_audio = Path(tmp.name)

    try:
        client.fget_object(
            bucket,
            audio_object_key,
            str(local_audio),
        )

        whisper = WhisperService(
            model_size="small",
            device="cpu",
            compute_type="int8",
        )

        segments = whisper.transcribe(local_audio)

        if not segments:
            return {
                "asset_id": asset_id,
                "segments": 0,
                "chunks": 0,
                "status": "NO_SPEECH",
            }

        normalized = TranscriptNormalizer().normalize(segments)

        chunks = TranscriptChunker().chunk(normalized)
        normalized = TranscriptNormalizer().normalize(segments)
        chunks = TranscriptChunker().chunk(normalized)
        video_id = asset.id
        retrieval = HybridRetrievalService(
            qdrant_url="http://qdrant:6333",
        )
        retrieval.index(
            chunks=chunks,
            video_id=video_id,
        )

        return {
            "asset_id": asset_id,
            "segments": len(segments),
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "start_ms": chunk.start_ms,
                    "end_ms": chunk.end_ms,
                    "text": chunk.text,
                    "normalized_text": chunk.normalized_text,
                    "source_segment_ids": chunk.source_segment_ids,
                    "confidence": chunk.confidence,
                }
                for chunk in chunks
            ],
            "status": "COMPLETED",
        }

    finally:
        if local_audio.exists():
            local_audio.unlink()
