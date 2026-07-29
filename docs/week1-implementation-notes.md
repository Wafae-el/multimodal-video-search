# Week 1 Implementation Notes

These notes describe the actual state of the Week 1 ingestion foundation as it
exists in the code. They separate what is completed, what is covered by tests,
and what is not. Nothing is claimed as "proven" unless a test exercises it.

## Scope

Week 1 delivers the ingestion foundation only: FastAPI + Pydantic contracts;
PostgreSQL + SQLAlchemy + Alembic; a Temporal durable workflow; MinIO storage; a
Docker Compose environment; ffprobe validation; idempotent probe / normalize /
audio / thumbnail activities; processing state, progress, attempts and last-error
tracking; worker-restart recovery and duplicate-delivery protection; and explicit
invalid-media and no-audio states. Scene detection, frame segmentation, ASR,
embeddings, retrieval, fusion, and UI are not part of Week 1.

## Completed

- **Consistent upload sequence** (`apps/api/main.py`, `packages/metadata/crud.py`):
  asset id generated before any external write; single-pass streaming computes
  checksum + size while enforcing the size limit; a durable validation record is
  created before validation completes; the original is stored at a deterministic
  per-asset key (`media-original/{asset_id}/original.{ext}`); the `media_files`
  row and asset finalization happen in one transaction; the deterministic
  workflow id (`process-asset-{asset_id}-{pipeline_version}`) is persisted before
  dispatch. Compensations: object deleted if the DB write fails after storage; a
  recoverable `UPLOADED` + `last_error` if Temporal dispatch fails. The filename
  is sanitized for display only, never used as identity.
- **Durable invalid / no-audio states**: invalid media (corrupt, unsupported,
  missing video stream, ffprobe failures, duration exceeded) is persisted as
  `FAILED` with a stable error code; valid video without audio is persisted as
  `NO_AUDIO` (a terminal Week 1 state — no workflow started). Both are observable
  via `GET /v1/assets/{asset_id}`.
- **Structured error contract**: a custom `APIError` + FastAPI exception handler
  return a flat `ErrorResponse` (`error`, `code`, optional `asset_id`); raw
  internal exceptions are never returned. Stable codes: `MEDIA_CORRUPT`,
  `MEDIA_UNSUPPORTED`, `MEDIA_NO_VIDEO_STREAM`, `MEDIA_NO_AUDIO`,
  `MEDIA_TOO_LARGE`, `MEDIA_DURATION_EXCEEDED`, `FFPROBE_TIMEOUT`,
  `FFPROBE_UNAVAILABLE`.
- **Typed workflow contract** (`packages/workflow/contracts.py`): the workflow
  takes `ProcessAssetInput(asset_id, pipeline_version)`; only stable identifiers
  and small string results enter Temporal history. Retry policy sets explicit
  timeouts, backoff, max attempts, and non-retryable error types.
- **Idempotent, retry-safe activities** (`packages/workflow/activities.py`,
  `operation_key.py`): canonical SHA-256 `operation_key`; a shared `_run_step`
  helper enters state monotonically, begins/resumes/reuses the step, reuses a
  completed output without re-running FFmpeg, verifies the written object, and
  advances state. Media-validation errors are non-retryable; other failures are
  retried and terminal `FAILED` is written only when non-retryable or attempts
  are exhausted. Concurrent duplicate deliveries are caught via a SAVEPOINT.
- **Complete output validation** (Part 10): probe validates the JSON + requires a
  video stream; normalize ffprobe-verifies the proxy; audio ffprobe-verifies PCM
  s16le / 16 kHz / mono; thumbnail checks the image is non-empty. Output failures
  raise a retryable `OutputValidationError`. Each derived artifact is persisted as
  an idempotent `media_files` row.
- **Attempt tracking**: `processing_steps.attempts` is incremented transactionally
  on each begin/resume, not on reuse; `media_assets.attempts` = the max attempt
  across steps. The status endpoint returns a per-step breakdown.
- **Blocking work handled correctly**: synchronous activities on a
  `ThreadPoolExecutor`; `-nostdin` + `stdin=DEVNULL`, timeouts, captured stderr,
  explicit return-code handling; isolated workspace per asset + operation key
  removed in `finally`; structured logs (`asset_id`, `workflow_id`, `activity`,
  `operation_key`, `attempt`); graceful shutdown; activity heartbeating.
- **State machine** (`state_machine.py`): strict `next_state` plus a
  `STATE_RANK`/`is_at_or_past` ordering for idempotent monotonic advancement.
- **Schema & migrations**: `media_assets`, `media_files`, `processing_steps`
  (unique `operation_key`; idempotency columns added in a second migration).
  `scripts/init_db.py` runs `alembic upgrade head`; no startup code creates tables.
- **Reproducible environment**: root `Dockerfile` (ffmpeg + deps), repaired
  Compose (pinned images, health checks, service-name networking), typed settings.

## Tested

Self-contained automated tests (`pytest`, no external services):

- `tests/unit/test_ffprobe.py` — ffprobe validation (valid, no-audio, missing
  video, corrupt, timeout, malformed JSON, unavailable).
- `tests/katas/crash_proof_castle/` — state-machine transitions, operation-key
  determinism, and the idempotent-event kata.
- `tests/integration/test_upload.py` — upload endpoint: valid (202 + deterministic
  workflow id + dispatch), no-audio persisted, corrupt/no-video → `FAILED`,
  unsupported MIME, too large, duration exceeded, recoverable dispatch failure,
  flat error shape (MinIO/Temporal/ffprobe mocked, SQLite).
- `tests/integration/test_idempotency.py` — via Temporal's `ActivityEnvironment`:
  repeat → one row/one artifact/FFmpeg-once/reuse; retry after state advanced (no
  invalid transition); pre-completed reuse; retryable-not-terminal-until-exhausted;
  non-retryable media error; attempt tracking.

Real-service integration tests (marked `integration`; skipped unless
`INTEGRATION=1`; real PostgreSQL/MinIO/Temporal + real ffmpeg; per-test cleanup):

- `test_upload_pipeline.py` — real video → `DONE`/100, four `COMPLETED` steps,
  four `media_files` rows, three non-empty derived objects at deterministic keys.
- `test_worker_restart.py` — kills the worker mid-activity (Docker SDK) and
  restarts it; asserts one step per operation key and one derived object per role.
- `test_duplicate_delivery.py` — same activity twice; second reused (no FFmpeg),
  one step, one object.
- `test_invalid_media.py` — `400 MEDIA_CORRUPT`, durable `FAILED`.
- `test_no_audio.py` — `422 MEDIA_NO_AUDIO`, durable `NO_AUDIO`.

CI (`.github/workflows/ci.yml`) runs lint, unit/kata/mocked-integration tests,
migration validation, a documentation artifact check, a Docker build, and the
real-service integration job.

## Not Yet Tested

- Concurrent duplicate delivery under real parallelism (the unique-key SAVEPOINT
  path is exercised only single-threaded in tests).

## Not Yet Implemented (Out of Week 1 Scope)

- Scene detection and frame segmentation
- ASR / transcript segmentation
- Embeddings and retrieval indexing
- Fusion and search
- Any user interface

Qdrant is provisioned by Docker Compose for later phases but is unused in Week 1.
