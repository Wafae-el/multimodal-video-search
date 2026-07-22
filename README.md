
 # Multimodal Video Search
 
 ## Overview
 
 Multimodal Video Search is a backend platform for ingesting and processing videos in preparation for multimodal retrieval.
 
 The Week 1 implementation provides the ingestion foundation with a durable processing pipeline based on FastAPI, PostgreSQL, MinIO, and Temporal.
 
 Implemented features:
 
 - FastAPI upload API
 - FFprobe video validation
 - PostgreSQL metadata persistence
 - MinIO object storage
 - Temporal durable workflow
 - Video processing state tracking
-- Scene detection
-- Representative frame extraction
+- Video normalization
 - Audio extraction
+- Thumbnail extraction
 - Docker Compose infrastructure
 
 ---
 
 ## Project Structure
 
 ```
 apps/
 workers/
 packages/
 infrastructure/
 migrations/
 tests/
 docs/
 ```
 
 ---
 
 ## Requirements
 
 - Python 3.12
 - Docker Desktop
 - FFmpeg (ffmpeg & ffprobe)
 
 ---
 
 ## Installation
 
 Install the project dependencies:
 
 ```bash
 pip install -r requirements.txt
 ```
 
 ---
 
 ## Start Infrastructure
 
-Start PostgreSQL, MinIO and Qdrant:
+Start PostgreSQL, MinIO, Temporal and Qdrant:
 
 ```bash
 cd infrastructure
 
 docker compose up -d
 ```
 
 ---
 
 ## Initialize the Database
 
 ```bash
 python -m scripts.init_db
 ```
 
 ---
 
 ## Start the API
 
 ```bash
 uvicorn apps.api.main:app --reload
 ```
 
 The API will be available at:
 
@@ -86,110 +86,110 @@ http://127.0.0.1:8000
 ```
 
 Swagger UI:
 
 ```
 http://127.0.0.1:8000/docs
 ```
 
 ---
 
 ## Start the Temporal Worker
 
 Open another terminal and run:
 
 ```bash
 python -m workers.ingestion.worker
 ```
 
 ---
 
 ## Upload a Video
 
 Use Swagger or send a POST request to:
 
 ```
-POST /upload
+POST /v1/upload
 ```
 
 After uploading a video, the processing workflow performs:
 
 1. Video validation
 2. FFprobe metadata extraction
 3. Metadata persistence
-4. Scene detection
-5. Representative frame extraction
-6. Audio extraction
+4. Video normalization
+5. Audio extraction
+6. Thumbnail extraction
 7. Workflow completion
 
 ---
 
 ## Running Tests
 
 Run all available tests:
 
 ```bash
 pytest
 ```
 
 Run only the Coding Quest tests:
 
 ```bash
 pytest tests/katas/crash_proof_castle
 ```
 
 ---
 
 ## Manual Verification
 
 To manually verify the pipeline:
 
 1. Start Docker services.
 2. Initialize the database.
 3. Start the FastAPI application.
 4. Start the Temporal worker.
 5. Open Swagger.
 6. Upload a video.
 
 Expected result:
 
 - Video uploaded successfully.
 - Metadata stored in PostgreSQL.
 - Workflow starts automatically.
-- Scenes are detected.
-- Representative frames are generated.
+- The video is normalized.
 - Audio is extracted.
+- A thumbnail is generated.
 - Workflow completes successfully.
 
 ---
 
 ## Technologies
 
 - FastAPI
 - PostgreSQL
 - SQLAlchemy
 - MinIO
 - Temporal
 - Qdrant
 - OpenCV
 - FFmpeg / FFprobe
 - Pydantic
 
 ---
 
 ## Week 1 Deliverables
 
 Completed:
 
 - Repository foundation
 - Docker Compose environment
 - FastAPI upload endpoint
 - FFprobe validation
 - PostgreSQL metadata persistence
 - MinIO object storage
 - Temporal durable workflow
 - Processing state tracking
-- Scene detection
-- Representative frame extraction
+- Video normalization
 - Audio extraction
+- Thumbnail extraction
 - Unit tests
-- Coding Quest 1
\ No newline at end of file
+- Coding Quest 1
