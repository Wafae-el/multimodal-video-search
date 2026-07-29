# Base image: pinned, supported slim Python.
FROM python:3.12.7-slim-bookworm

# System dependencies:
#   - ffmpeg provides both `ffmpeg` and `ffprobe`, required by the media pipeline.
#   - curl is used by the container health checks in docker-compose.
# psycopg is installed as a binary wheel (psycopg[binary]), so no PostgreSQL
# build/client packages are required.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source.
COPY . .

EXPOSE 8000

# Default command runs the API. The worker overrides this via docker-compose:
#   python -m workers.ingestion.worker
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
