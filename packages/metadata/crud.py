from sqlalchemy.orm import Session

from packages.metadata.models import Video


def create_video(
    db: Session,
    filename: str,
    content_type: str,
    duration: float,
    codec: str,
    width: int,
    height: int,
    size: int,
):

    video = Video(
        filename=filename,
        content_type=content_type,
        duration=duration,
        codec=codec,
        width=width,
        height=height,
        size=size,
        status="UPLOADED",
        progress=0,
        attempts=1,
    )

    db.add(video)
    db.commit()
    db.refresh(video)

    return video


def update_video_status(
    db: Session,
    video_id: int,
    status: str,
    progress: int = None,
    last_error: str = None,
):
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        return None

    video.status = status

    if progress is not None:
        video.progress = progress

    if last_error is not None:
        video.last_error = last_error

    db.commit()
    db.refresh(video)

    return video