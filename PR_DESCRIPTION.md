# Week 1 — Ingestion Foundation (corrections)

## 1. Summary

This PR corrects the remaining Week 1 blockers and brings the ingestion
foundation to a durable, idempotent, tested state: a consistent upload sequence,
durable invalid/no-audio states, state-safe Temporal retries, production
idempotency with verified artifacts, correct attempt tracking, correct handling
of blocking work, a buildable Docker environment, Alembic-owned schema, real
integration tests, and CI. No Week 2+ features (scene detection, ASR, embeddings,
retrieval, fusion, UI) were added.

## 2. Week 1 Scope

FastAPI + Pydantic contracts; PostgreSQL + SQLAlchemy + Alembic; Temporal durable
workflow; MinIO/S3 storage; Docker Compose; ffprobe validation; idempotent probe,
normalize, audio, thumbnail activities; processing state/progress/attempts/error;
worker-restart recovery; duplicate-delivery protection; explicit invalid-media
and no-audio states.

## 3. Architecture Decisions

- **Identity before side effects**: `asset_id` (UUID) is generated first; the
  filename is never used as identity.
- **Durable validation record**: the asset row is created before validation
  completes so invalid/no-audio outcomes are observable via the status API.
- **One-transaction finalize + compensations**: `media_files` insert and asset
  finalize are atomic; the object is deleted if the DB write fails, and the asset
  is left recoverable if Temporal dispatch fails.
- **Minimal Temporal payloads**: only `asset_id` + `pipeline_version` travel
  through history — no paths, blobs, or media.
- **Canonical operation key**: SHA-256 over canonical JSON (no ambiguous
  concatenation); unique DB constraint; SAVEPOINT-guarded concurrent inserts.
- **Monotonic state advancement**: retries never raise invalid-transition errors.
- **Terminal FAILED only when non-retryable or attempts exhausted.**
- **Deterministic derived keys**: `proxy/720p.mp4`, `audio/source.wav`,
  `thumbnail/default.jpg`; each artifact ffprobe/size-verified before completion.
- **Blocking work off the event loop**: synchronous activities on a thread pool;
  heartbeating for fast dead-worker detection; graceful shutdown.
- **`NO_AUDIO` is a terminal Week 1 state** (visual-only processing deferred).
- **`media_assets.attempts` = max attempt across steps** (per-step breakdown in
  the status API).

## 4. Files / Components Changed

- `Dockerfile`, `.dockerignore` (new); `infrastructure/docker-compose.yml`
  (build context, pinned images, health checks, service-name networking).
- `apps/api/main.py` (upload consistency, error contract, status + steps).
- `packages/workflow/` — `activities.py`, `workflows.py`, `state_machine.py`,
  `contracts.py` (new), `operation_key.py` (new).
- `packages/metadata/` — `models.py`, `crud.py`; Alembic migration
  `b1a2c3d4e5f6_processing_step_idempotency.py` (new); initial migration renamed
  `videos` → `media_assets`.
- `packages/media/` — `ffprobe_service.py`, `normalizer.py`, `thumbnail_service.py`;
  `packages/segmentation/audio_extractor.py`; `packages/storage/minio_service.py`.
- `packages/config/settings.py`; `scripts/init_db.py`; `workers/ingestion/worker.py`.
- `tests/integration/` (new: conftest + 7 files); `.github/workflows/ci.yml`,
  `ruff.toml` (new); `README.md`, `docs/week1-implementation-notes.md`.
- Removed committed `test.db`; `.gitignore` updated.

## 5. Migration Instructions

```bash
alembic upgrade head            # or: python -m scripts.init_db
# in Docker:
docker compose -f infrastructure/docker-compose.yml run --rm api python -m scripts.init_db
alembic downgrade base          # reverses cleanly
```

## 6. Local Startup

```bash
cp .env.example .env
docker compose -f infrastructure/docker-compose.yml up -d
docker compose -f infrastructure/docker-compose.yml run --rm api python -m scripts.init_db
# API http://127.0.0.1:8000/docs, Temporal UI :8080, MinIO console :9001
```

## 7. Tests Executed

- `ruff check .` → clean.
- `pytest` (unit + katas + mocked integration) → 38 passed, 5 skipped.
- Real-service integration (`INTEGRATION=1`) → 5 passed (upload pipeline, worker
  restart, duplicate delivery, invalid media, no audio).
- `docker compose config/build/up`, `alembic upgrade head`/`downgrade base` → OK.

## 8. Restart-Demo Procedure

1. Start the stack, migrate, upload a video.
2. While processing, `docker compose ... restart worker` (or the automated test
   kills the worker mid-activity).
3. The workflow resumes; the final result has exactly one `COMPLETED` step per
   operation key and one derived object per role.
   Automated: `tests/integration/test_worker_restart.py`.

## 9. Idempotency Proof

`tests/integration/test_duplicate_delivery.py` invokes the same activity twice
against real services: the second delivery is reused (no FFmpeg re-run), leaving
one completed `processing_steps` row and one derived object.
`test_idempotency.py` proves the same at activity level.

## 10. Known Limitations

- Concurrent duplicate delivery under real parallelism is handled but exercised
  only single-threaded in tests.
- `NO_AUDIO` is terminal in Week 1 (no visual-only processing).
- Qdrant is provisioned but unused in Week 1.

## 11. Acceptance Checklist

- [x] Docker Compose stack builds
- [x] Alembic migration works
- [x] Upload persists source in MinIO
- [x] ffprobe returns stable errors
- [x] Temporal receives only asset_id and pipeline_version
- [x] Probe is idempotent
- [x] Normalize is idempotent
- [x] Audio extraction is idempotent
- [x] Thumbnail generation is idempotent
- [x] Status API exposes state/progress/attempts/error
- [x] Worker restart test passes
- [x] Duplicate delivery test passes
- [x] Invalid media test passes
- [x] No-audio test passes
- [ ] CI passes (runs on push to the PR; not yet observed green on GitHub)
