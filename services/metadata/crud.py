from sqlalchemy.orm import Session

from services.metadata.models import Video


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
    )

    db.add(video)
    db.commit()
    db.refresh(video)

    return video