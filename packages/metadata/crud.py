from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from packages.metadata.models import (
    Video,
    MediaFile,
    ProcessingStep,
    Scene,
)
from packages.workflow.state_machine import (
    ProcessingState,
    TERMINAL_STATES,
    is_at_or_past,
)
from packages.metadata.models import SceneFrame


def create_asset(
    db: Session,
    **kwargs,
):
    try:
        asset = Video(**kwargs)
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset
    except SQLAlchemyError:
        db.rollback()
        raise


def register_original_media(
    db: Session,
    video_id: int,
    bucket: str,
    object_key: str,
    checksum: str,
):
    try:
        media = MediaFile(
            video_id=video_id,
            file_type="original",
            bucket=bucket,
            object_key=object_key,
            checksum=checksum,
        )

        db.add(media)
        db.commit()
        db.refresh(media)

        return media

    except SQLAlchemyError:
        db.rollback()
        raise


def get_asset_status(
    db: Session,
    asset_id: str,
):
    return (
        db.query(Video)
        .filter(Video.asset_id == asset_id)
        .first()
    )


def create_pending_asset(
    db: Session,
    *,
    asset_id: str,
    filename: str,
    content_type: str,
    source_checksum: str,
    size: int,
    pipeline_version: str,
    status: str,
):
    """Persist the durable validation record before media validation completes.

    This guarantees that invalid / no-audio outcomes remain observable through
    ``GET /v1/assets/{asset_id}`` instead of being lost. Storage location and
    probed metadata are filled in later by :func:`finalize_original_upload`.
    """
    try:
        asset = Video(
            asset_id=asset_id,
            filename=filename,
            content_type=content_type,
            source_checksum=source_checksum,
            size=size,
            pipeline_version=pipeline_version,
            status=status,
            progress=0,
            attempts=0,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset
    except SQLAlchemyError:
        db.rollback()
        raise


def mark_asset_failed(
    db: Session,
    asset_id: str,
    *,
    status: str,
    error_code: str,
    progress: int | None = None,
):
    """Persist a terminal outcome (FAILED / NO_AUDIO) with a stable error code so
    the state remains recoverable and traceable. ``progress=None`` keeps the
    current progress (used for mid-pipeline failures)."""
    try:
        asset = (
            db.query(Video)
            .filter(Video.asset_id == asset_id)
            .first()
        )
        if asset is None:
            return None

        asset.status = status
        asset.last_error = error_code
        if progress is not None:
            asset.progress = progress

        db.commit()
        db.refresh(asset)
        return asset
    except SQLAlchemyError:
        db.rollback()
        raise


def finalize_original_upload(
    db: Session,
    asset_id: str,
    *,
    bucket: str,
    object_key: str,
    duration: float,
    duration_ms: int,
    codec: str,
    width: int,
    height: int,
    workflow_id: str,
    status: str,
):
    """Atomically record the stored original.

    In a single transaction this updates the asset with its probed metadata,
    storage location and intended workflow id, and inserts the matching
    ``media_files`` row. Either both succeed or neither does, so every stored
    object is traceable to a ``media_files`` row and the workflow id is
    persisted before dispatch.
    """
    try:
        asset = (
            db.query(Video)
            .filter(Video.asset_id == asset_id)
            .first()
        )
        if asset is None:
            raise ValueError("ASSET_NOT_FOUND")

        asset.duration = duration
        asset.duration_ms = duration_ms
        asset.codec = codec
        asset.width = width
        asset.height = height
        asset.minio_bucket = bucket
        asset.minio_object_key = object_key
        asset.workflow_id = workflow_id
        asset.status = status

        media = MediaFile(
            video_id=asset.id,
            file_type="original",
            bucket=bucket,
            object_key=object_key,
            checksum=asset.source_checksum,
        )
        db.add(media)

        db.commit()
        db.refresh(asset)
        return asset
    except SQLAlchemyError:
        db.rollback()
        raise


def set_asset_error(
    db: Session,
    asset_id: str,
    *,
    error_code: str,
):
    """Record a recoverable error (e.g. workflow dispatch failure) without
    changing the asset state, so a later retry can resume from a known point."""
    try:
        asset = (
            db.query(Video)
            .filter(Video.asset_id == asset_id)
            .first()
        )
        if asset is None:
            return None

        asset.last_error = error_code
        db.commit()
        db.refresh(asset)
        return asset
    except SQLAlchemyError:
        db.rollback()
        raise


def increment_attempts(
    db: Session,
    asset_id: str,
):
    try:
        asset = (
            db.query(Video)
            .filter(Video.asset_id == asset_id)
            .first()
        )

        if asset is None:
            return None

        asset.attempts += 1

        db.commit()
        db.refresh(asset)

        return asset

    except SQLAlchemyError:
        db.rollback()
        raise


def start_processing_step(
    db: Session,
    video_id: int,
    step_name: str,
    step_version: str,
    operation_key: str,
):
    try:
        existing = (
            db.query(ProcessingStep)
            .filter(
                ProcessingStep.operation_key == operation_key
            )
            .first()
        )

        if existing:
            return existing

        step = ProcessingStep(
            video_id=video_id,
            step_name=step_name,
            step_version=step_version,
            operation_key=operation_key,
            state="RUNNING",
            attempts=1,
        )

        db.add(step)
        db.commit()
        db.refresh(step)

        return step

    except SQLAlchemyError:
        db.rollback()
        raise


def complete_processing_step(
    db: Session,
    operation_key: str,
    output_key: str,
    output_checksum: str,
):
    try:
        step = (
            db.query(ProcessingStep)
            .filter(
                ProcessingStep.operation_key == operation_key
            )
            .first()
        )

        if step is None:
            return None

        step.state = "COMPLETED"
        step.output_key = output_key
        step.output_checksum = output_checksum

        db.commit()
        db.refresh(step)

        return step

    except SQLAlchemyError:
        db.rollback()
        raise


def fail_processing_step(
    db: Session,
    operation_key: str,
    error: str,
):
    try:
        step = (
            db.query(ProcessingStep)
            .filter(
                ProcessingStep.operation_key == operation_key
            )
            .first()
        )

        if step is None:
            return None

        step.state = "FAILED"
        step.last_error = error
        step.attempts += 1

        db.commit()
        db.refresh(step)

        return step

    except SQLAlchemyError:
        db.rollback()
        raise


def reuse_completed_operation(
    db: Session,
    operation_key: str,
):
    return (
        db.query(ProcessingStep)
        .filter(
            ProcessingStep.operation_key == operation_key,
            ProcessingStep.state == "COMPLETED",
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Retry-safe processing-step lifecycle (Parts 6 & 7).
# ---------------------------------------------------------------------------

def _step_snapshot(step: ProcessingStep, status: str) -> dict:
    return {
        "status": status,  # "completed" | "run"
        "output_bucket": step.output_bucket,
        "output_key": step.output_key,
        "output_checksum": step.output_checksum,
        "attempts": step.attempts,
    }


def begin_or_resume_step(
    db: Session,
    *,
    video_id: int,
    step_name: str,
    step_version: str,
    tool_version: str,
    input_checksum: str,
    operation_key: str,
) -> dict:
    """Begin, resume or short-circuit a processing step by its operation key.

    Returns a snapshot dict whose ``status`` is:
      - ``"completed"`` if a COMPLETED row already exists (duplicate delivery /
        output-exists) — the caller reuses the stored output instead of working.
      - ``"run"`` otherwise; a new row is created (RUNNING, attempt 1) or an
        existing RUNNING/FAILED/PENDING row is resumed (state RUNNING, attempts
        incremented). A stale RUNNING row from a crashed worker is safely
        resumed the same way.

    A concurrent duplicate delivery that loses the unique-key race is caught as
    duplicate delivery (via a SAVEPOINT) rather than surfacing as a server error.

    When execution actually begins (a "run" outcome), the asset-level
    ``attempts`` is raised to the maximum step attempt count in the same
    transaction. It is NOT bumped when a completed output is reused.
    """
    def _bump_asset_attempts(step_attempts: int) -> None:
        asset = db.query(Video).filter(Video.id == video_id).first()
        if asset is not None and (asset.attempts or 0) < step_attempts:
            asset.attempts = step_attempts

    existing = (
        db.query(ProcessingStep)
        .filter(ProcessingStep.operation_key == operation_key)
        .first()
    )
    if existing is not None:
        if existing.state == "COMPLETED":
            return _step_snapshot(existing, "completed")
        existing.state = "RUNNING"
        existing.attempts = (existing.attempts or 0) + 1
        existing.last_error = None
        _bump_asset_attempts(existing.attempts)
        db.commit()
        db.refresh(existing)
        return _step_snapshot(existing, "run")

    step = ProcessingStep(
        video_id=video_id,
        step_name=step_name,
        step_version=step_version,
        tool_version=tool_version,
        input_checksum=input_checksum,
        operation_key=operation_key,
        state="RUNNING",
        attempts=1,
    )
    try:
        with db.begin_nested():
            db.add(step)
            db.flush()
    except IntegrityError:
        # Lost the race: another delivery inserted the same operation_key.
        db.rollback()
        existing = (
            db.query(ProcessingStep)
            .filter(ProcessingStep.operation_key == operation_key)
            .first()
        )
        if existing is not None and existing.state == "COMPLETED":
            return _step_snapshot(existing, "completed")
        if existing is not None:
            return _step_snapshot(existing, "run")
        raise

    _bump_asset_attempts(step.attempts)
    db.commit()
    db.refresh(step)
    return _step_snapshot(step, "run")


def complete_step(
    db: Session,
    operation_key: str,
    *,
    output_bucket: str | None,
    output_key: str | None,
    output_checksum: str | None,
):
    try:
        step = (
            db.query(ProcessingStep)
            .filter(ProcessingStep.operation_key == operation_key)
            .first()
        )
        if step is None:
            return None

        step.state = "COMPLETED"
        step.output_bucket = output_bucket
        step.output_key = output_key
        step.output_checksum = output_checksum
        step.last_error = None

        db.commit()
        db.refresh(step)
        return step
    except SQLAlchemyError:
        db.rollback()
        raise


def fail_step(
    db: Session,
    operation_key: str,
    *,
    error: str,
):
    """Record a step failure. The step stays resumable (a later attempt will set
    it back to RUNNING); attempts are not incremented here because they are
    incremented in :func:`begin_or_resume_step`."""
    try:
        step = (
            db.query(ProcessingStep)
            .filter(ProcessingStep.operation_key == operation_key)
            .first()
        )
        if step is None:
            return None

        step.state = "FAILED"
        step.last_error = error

        db.commit()
        db.refresh(step)
        return step
    except SQLAlchemyError:
        db.rollback()
        raise


def advance_asset_state(
    db: Session,
    asset_id: str,
    *,
    target: ProcessingState,
    progress: int | None = None,
):
    """Idempotent, monotonic forward transition.

    No-op if the asset is already at or past ``target`` (safe re-entry for
    Temporal retries and duplicate deliveries) and never moves backwards or out
    of a terminal state. Clears ``last_error`` on real forward progress
    (superseding a previous failure after a successful retry).
    """
    try:
        asset = (
            db.query(Video)
            .filter(Video.asset_id == asset_id)
            .first()
        )
        if asset is None:
            raise ValueError("ASSET_NOT_FOUND")

        current = ProcessingState(asset.status)
        if current in TERMINAL_STATES:
            return asset

        if is_at_or_past(current, target):
            # Already advanced; only nudge progress forward, never backward.
            if progress is not None and progress > (asset.progress or 0):
                asset.progress = progress
                db.commit()
                db.refresh(asset)
            return asset

        asset.status = target.value
        if progress is not None:
            asset.progress = progress
        asset.last_error = None

        db.commit()
        db.refresh(asset)
        return asset
    except SQLAlchemyError:
        db.rollback()
        raise


def register_media_file(
    db: Session,
    *,
    video_id: int,
    file_type: str,
    bucket: str,
    object_key: str,
    checksum: str,
):
    """Idempotently record a derived media file (one row per (video, file_type)),
    so retries do not create duplicate media_files rows."""
    try:
        existing = (
            db.query(MediaFile)
            .filter(
                MediaFile.video_id == video_id,
                MediaFile.file_type == file_type,
            )
            .first()
        )
        if existing is not None:
            existing.bucket = bucket
            existing.object_key = object_key
            existing.checksum = checksum
            db.commit()
            db.refresh(existing)
            return existing

        media = MediaFile(
            video_id=video_id,
            file_type=file_type,
            bucket=bucket,
            object_key=object_key,
            checksum=checksum,
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        return media
    except SQLAlchemyError:
        db.rollback()
        raise


def get_processing_steps(db: Session, asset_id: str):
    """Return the processing steps for an asset (ordered), for status reporting."""
    asset = (
        db.query(Video)
        .filter(Video.asset_id == asset_id)
        .first()
    )
    if asset is None:
        return []
    return (
        db.query(ProcessingStep)
        .filter(ProcessingStep.video_id == asset.id)
        .order_by(ProcessingStep.id)
        .all()
    )

def create_scene(
    db: Session,
    *,
    video_id: int,
    scene_index: int,
    start_ms: int,
    end_ms: int,
    duration_ms: int,
):
    try:
        scene = Scene(
            video_id=video_id,
            scene_index=scene_index,
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=duration_ms,
        )

        db.add(scene)
        db.commit()
        db.refresh(scene)

        return scene

    except SQLAlchemyError:
        db.rollback()
        raise


def get_scenes(
    db: Session,
    video_id: int,
):
    return (
        db.query(Scene)
        .filter(Scene.video_id == video_id)
        .order_by(Scene.scene_index)
        .all()
    )

def create_scene_frame(
    db: Session,
    *,
    scene_id: int,
    timestamp_ms: int,
    bucket: str,
    object_key: str,
    checksum: str,
):
    try:
        existing = (
            db.query(SceneFrame)
            .filter(
                SceneFrame.scene_id == scene_id,
                SceneFrame.timestamp_ms == timestamp_ms,
            )
            .first()
        )

        if existing is not None:
            return existing

        frame = SceneFrame(
            scene_id=scene_id,
            timestamp_ms=timestamp_ms,
            bucket=bucket,
            object_key=object_key,
            checksum=checksum,
        )

        db.add(frame)
        db.commit()
        db.refresh(frame)

        return frame

    except SQLAlchemyError:
        db.rollback()
        raise

def get_scene_frames(
    db: Session,
    scene_id: int,
):
    return (
        db.query(SceneFrame)
        .filter(SceneFrame.scene_id == scene_id)
        .all()
    )
