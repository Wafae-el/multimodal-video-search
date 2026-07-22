import os


LOCAL_INIT_ENV = {
    "DATABASE_URL": "sqlite:///./test.db",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "minioadmin",
    "MINIO_SECRET_KEY": "minioadmin",
    "MINIO_BUCKET": "media",
    "TEMPORAL_ADDRESS": "localhost:7233",
    "QDRANT_URL": "http://localhost:6333",
}

for name, value in LOCAL_INIT_ENV.items():
    os.environ.setdefault(name, value)

from packages.metadata import models  # noqa: E402,F401
from packages.metadata.database import Base, engine  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database schema initialized.")


if __name__ == "__main__":
    main()