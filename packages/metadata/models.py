from sqlalchemy import Column, Integer, String, Float

from packages.metadata.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)

    duration = Column(Float)
    codec = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    size = Column(Integer)

    # Processing state
    status = Column(String, default="UPLOADED")
    progress = Column(Integer, default=0)
    attempts = Column(Integer, default=0)
    last_error = Column(String, nullable=True)

    