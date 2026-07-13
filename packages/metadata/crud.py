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
    print(">>> Creating video in PostgreSQL")

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
    print(">>> Added to session")

    db.commit()
    print(">>> Commit OK")

    db.refresh(video)
    print(">>> Video ID:", video.id)

    return video