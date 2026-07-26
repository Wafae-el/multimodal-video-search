from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str

    # MinIO
    MINIO_ENDPOINT: str
    MINIO_PORT: int = 9000
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str
    MINIO_SECURE: bool = False

    # Temporal
    TEMPORAL_ADDRESS: str
    TEMPORAL_TASK_QUEUE: str = "video-processing"

    # Qdrant
    QDRANT_URL: str

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Upload configuration
    MAX_UPLOAD_SIZE: int = Field(default=500 * 1024 * 1024)
    ALLOWED_CONTENT_TYPES: str = (
        "video/mp4,video/x-matroska,video/quicktime,video/x-msvideo"
    )

    # Pipeline
    PIPELINE_VERSION: str = "v1"

    # SQLAlchemy
    SQL_ECHO: bool = False
    SQL_POOL_PRE_PING: bool = True

     # Logging
    LOG_LEVEL: str = "INFO"
    APP_ENV: str = "development"

    # Derived bucket (pour les fichiers transformés)
    DERIVED_BUCKET: str = "media-derived"   # <-- Ajout
    # Derived bucket for transformed files
    DERIVED_BUCKET: str = "media-derived"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )



settings = Settings()

