# Multimodal Video Search

## Project Purpose

Multimodal Video Search is a backend platform for ingesting and processing
videos in preparation for multimodal retrieval.

This repository contains the **Week 1 ingestion foundation**: a durable,
idempotent processing pipeline that validates an uploaded video, persists its
metadata, stores it in object storage, and runs a Temporal workflow that
normalizes the video and produces derived artifacts (a 720p proxy, extracted
audio, and a thumbnail). Retrieval, embeddings, scene detection, ASR, and search
are **not** part of Week 1 and are not implemented.

## Week 1 Scope

Implemented:

- FastAPI upload API with Pydantic request/response contracts
- ffprobe media validation with stable error codes
- PostgreSQL metadata persistence via SQLAlchemy, with Alembic migrations
- MinIO / S3-compatible object storage (original + derived artifacts)
- Temporal durable workflow orchestrating idempotent activities
- Idempotent, retry-safe activities: probe, normalize, audio extraction, thumbnail
- Processing state machine with progress, attempts, and last-error tracking
- Worker-restart recovery and duplicate-delivery protection
- Explicit, durable invalid-media and no-audio states
- Docker Compose environment + Dockerfile for reproducible runs
- Unit, self-contained, and real-service integration tests, plus CI

Explicitly **out of scope**: scene detection, frame segmentation, ASR,
embeddings, retrieval, fusion, and UI.

## Architecture Overview

```
Client ──POST /v1/upload──▶ FastAPI (apps/api)
                              │ 1. generate asset_id (identity before any write)
                              │ 2. stream to disk: checksum + size + limit
                              │ 3. create durable validation record (VALIDATING)
                              │ 4. ffprobe validation
                              │ 5. store original in MinIO (deterministic key)
                              │ 6. media_files row + finalize asset (one txn)
                              │ 7. start Temporal workflow (only asset_id + version)
                              ▼
                        Temporal Server
                              ▼
                 Worker (workers/ingestion, sync activities on a thread pool)
                 ProcessAssetWorkflow:
                   probe_video ─▶ normalize_video ─▶ extract_audio ─▶ generate_thumbnail
```

Each activity is idempotent and retry-safe: it derives a canonical
`operation_key` (SHA-256 over canonical JSON of source checksum, step, step
version, tool version). Completed steps are recorded in `processing_steps`
(unique constraint on `operation_key`); a repeated delivery returns the stored
output **without running FFmpeg again**. Each produced artifact is ffprobe/size
verified before the step is marked complete and recorded as a `media_files` row.
State is advanced monotonically, so a retry that finds the asset already
advanced never raises an invalid-transition error. Derived keys are deterministic:
`media-derived/{asset_id}/proxy/720p.mp4`, `.../audio/source.wav`,
`.../thumbnail/default.jpg`.

### Repository Layout

```
apps/api/              FastAPI application (upload + status endpoints)
workers/ingestion/     Temporal worker (sync activities + thread pool)
packages/config/       Typed settings (pydantic-settings)
packages/media/        ffprobe validation, normalizer, thumbnail service
packages/segmentation/ audio extraction
packages/storage/      MinIO client and helpers
packages/metadata/     SQLAlchemy models, session, CRUD
packages/workflow/     Temporal workflow, activities, state machine, operation key, contracts
alembic/               Database migrations
infrastructure/        docker-compose.yml
tests/unit, tests/katas, tests/integration
.github/workflows/     CI
```

## Prerequisites

- Python 3.12
- Docker Desktop (for Docker Compose)
- FFmpeg, providing both `ffmpeg` and `ffprobe` (bundled in the image)

## Environment Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env.example` uses Docker service hostnames (`postgres`, `minio`, `temporal`)
and the psycopg (v3) driver scheme `postgresql+psycopg://...`. When running the
API or worker outside Docker, point the URLs at `localhost`.

## Docker Compose Startup

```bash
docker compose -f infrastructure/docker-compose.yml up -d
```

Service endpoints (defaults): API http://127.0.0.1:8000 (Swagger at `/docs`),
MinIO console http://127.0.0.1:9001, Temporal Web UI http://127.0.0.1:8080.
Qdrant is started to reserve its port for later phases but is unused in Week 1.

## Alembic Migrations

The schema is owned by Alembic; the app never creates tables at startup. Alembic
reads `DATABASE_URL` from the typed settings.

```bash
alembic upgrade head          # apply
python -m scripts.init_db     # official entry point (wraps `alembic upgrade head`)
alembic downgrade base        # roll back
```

In Docker: `docker compose -f infrastructure/docker-compose.yml run --rm api python -m scripts.init_db`.

## API Startup

```bash
uvicorn apps.api.main:app --reload
```

## Worker Startup

```bash
python -m workers.ingestion.worker
```

The activities are **synchronous** and run on a thread-pool executor
(`WORKER_ACTIVITY_THREADS`, default 8), so a long FFmpeg job never blocks the
Temporal event loop. The worker handles SIGINT/SIGTERM and shuts down gracefully
(`WORKER_GRACEFUL_SHUTDOWN_SECONDS`). Long activities heartbeat so a killed
worker is detected within `heartbeat_timeout` (10 s) and rescheduled.

## Upload Example

```bash
curl -X POST http://127.0.0.1:8000/v1/upload \
  -F "file=@/path/to/video.mp4;type=video/mp4"
```

Accepted content types: `video/mp4`, `video/x-matroska`, `video/quicktime`,
`video/x-msvideo`. Max upload size: 500 MB. Success returns `202 Accepted`:

```json
{
  "asset_id": "3f1c2b7e-....",
  "workflow_id": "process-asset-3f1c2b7e-....-v1",
  "status": "UPLOADED"
}
```

Errors return a flat `ErrorResponse` (`error`, `code`, and `asset_id` when a
durable record was created):

| Case | HTTP | code |
| --- | --- | --- |
| Unsupported MIME/extension | 415 | `MEDIA_UNSUPPORTED` |
| Too large | 413 | `MEDIA_TOO_LARGE` |
| Corrupt media | 400 | `MEDIA_CORRUPT` |
| No video stream | 422 | `MEDIA_NO_VIDEO_STREAM` |
| No audio stream | 422 | `MEDIA_NO_AUDIO` |
| Duration exceeded | 422 | `MEDIA_DURATION_EXCEEDED` |
| ffprobe timeout / unavailable | 503 | `FFPROBE_TIMEOUT` / `FFPROBE_UNAVAILABLE` |

Invalid media is persisted as `FAILED`, and valid video without audio as
`NO_AUDIO` (a terminal Week 1 state — no workflow is started). Both are
observable via `GET /v1/assets/{asset_id}`.

## Asset-Status Example

```bash
curl http://127.0.0.1:8000/v1/assets/<asset_id>
```

```json
{
  "asset_id": "3f1c2b7e-....",
  "status": "DONE",
  "progress": 100,
  "attempts": 1,
  "last_error": null,
  "steps": [
    {"step_name": "probe", "state": "COMPLETED", "attempts": 1},
    {"step_name": "normalize", "state": "COMPLETED", "attempts": 1},
    {"step_name": "extract_audio", "state": "COMPLETED", "attempts": 1},
    {"step_name": "thumbnail", "state": "COMPLETED", "attempts": 1}
  ]
}
```

States: `UPLOADED → VALIDATING → PROBING → NORMALIZING → EXTRACTING_AUDIO →
GENERATING_THUMBNAIL → DONE`, terminal `FAILED` and `NO_AUDIO`. `attempts` is the
maximum attempt count across steps (1 on a clean run, higher after a retry).

## Test Commands

Self-contained tests (MinIO/Temporal/ffprobe mocked, SQLite — no services):

```bash
pytest                         # unit + katas + mocked integration; real-service tests skip
ruff check .
```

### Real-service integration tests

`tests/integration/test_{upload_pipeline,worker_restart,duplicate_delivery,invalid_media,no_audio}.py`
use real PostgreSQL/MinIO/Temporal with real ffmpeg. Marked `integration`,
skipped unless `INTEGRATION=1`. With the stack up and migrated, run them in a
container joined to the Compose network (the restart test controls the worker via
the Docker socket):

```bash
docker run --rm --network infrastructure_default \
  -v "$PWD:/app" -w /app \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e INTEGRATION=1 \
  -e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/video_search \
  -e MINIO_ENDPOINT=minio:9000 -e MINIO_ACCESS_KEY=minioadmin \
  -e MINIO_SECRET_KEY=minioadmin -e MINIO_BUCKET=media \
  -e TEMPORAL_ADDRESS=temporal:7233 -e QDRANT_URL=http://qdrant:6333 \
  -e API_BASE_URL=http://api:8000 \
  infrastructure-worker:latest \
  sh -c "pip install -q docker && pytest tests/integration -m integration -v"
```

## Restart / Idempotency Demonstration

1. Start the stack, apply migrations, upload a video.
2. While it is processing, restart the worker
   (`docker compose -f infrastructure/docker-compose.yml restart worker`).
3. The workflow resumes; already-completed activities reuse their stored outputs.
   The final result has exactly one `COMPLETED` `processing_steps` row per
   operation key and one derived object per role.

This is covered by `tests/integration/test_worker_restart.py` (kills the worker
mid-activity and asserts the invariants) and `test_idempotency.py`
(activity-level).

## Known Limitations

- Concurrent duplicate delivery under real parallelism is handled (unique-key
  SAVEPOINT) but exercised only single-threaded in tests.
- No-audio media is a terminal `NO_AUDIO` asset (no visual-only processing in
  Week 1).
- Qdrant is provisioned by Docker Compose but unused in Week 1.
- No embeddings, retrieval, search, scene detection, ASR, or UI (out of scope).
