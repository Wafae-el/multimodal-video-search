from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from packages.metadata.models import (
    Video,
    MediaFile,
    ProcessingStep,
)
from packages.workflow.state_machine import ProcessingState


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