import os


DEFAULT_TEST_ENV = {
    "DATABASE_URL": "sqlite:///./test.db",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "minioadmin",
    "MINIO_SECRET_KEY": "minioadmin",
    "MINIO_BUCKET": "media",
    "TEMPORAL_ADDRESS": "localhost:7233",
    "QDRANT_URL": "http://localhost:6333",
}


for name, value in DEFAULT_TEST_ENV.items():
    os.environ.setdefault(name, value)
