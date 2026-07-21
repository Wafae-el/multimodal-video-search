import uuid

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from packages.metadata.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)

    asset_id = Column(
        String,
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)

    duration = Column(Float)
    duration_ms = Column(Integer)

    codec = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    size = Column(Integer)

    source_checksum = Column(String, nullable=False)

    pipeline_version = Column(
        String,
        nullable=False,
        default="v1",
    )

    workflow_id = Column(String)

    minio_bucket = Column(String)
    minio_object_key = Column(String)

    status = Column(String, default="UPLOADED")
    progress = Column(Integer, default=0)
    attempts = Column(Integer, default=0)
    last_error = Column(String)

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    media_files = relationship(
        "MediaFile",
        back_populates="video",
        cascade="all, delete-orphan",
    )

    processing_steps = relationship(
        "ProcessingStep",
        back_populates="video",
        cascade="all, delete-orphan",
    )


class MediaFile(Base):
    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True)

    video_id = Column(
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )

    file_type = Column(String, nullable=False)

    bucket = Column(String, nullable=False)

    object_key = Column(String, nullable=False)

    checksum = Column(String, nullable=False)

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )

    video = relationship(
        "Video",
        back_populates="media_files",
    )


class ProcessingStep(Base):
    __tablename__ = "processing_steps"

    __table_args__ = (
        UniqueConstraint(
            "operation_key",
            name="uq_processing_operation_key",
        ),
    )

    id = Column(Integer, primary_key=True)

    video_id = Column(
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )

    step_name = Column(String, nullable=False)

    step_version = Column(String, nullable=False)

    operation_key = Column(
        String,
        nullable=False,
    )

    state = Column(
        String,
        nullable=False,
        default="PENDING",
    )

    attempts = Column(
        Integer,
        default=0,
    )

    output_key = Column(String)

    output_checksum = Column(String)

    last_error = Column(String)

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    video = relationship(
        "Video",
        back_populates="processing_steps",
    )