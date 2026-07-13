# Multimodal Video Search

## Overview

Multimodal Video Search is a backend service for ingesting and processing videos.

The Week 1 implementation provides:

- FastAPI upload API
- ffprobe video validation
- PostgreSQL metadata storage
- MinIO object storage
- Temporal workflow foundation
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

- Docker Desktop
- Python 3.12
- FFmpeg (ffprobe)

---

## Install

```bash
pip install -r requirements.txt
```

---

## Start Docker

```bash
cd infrastructure

docker compose up -d
```

---

## Initialize database

```bash
python -m scripts.init_db
```

---

## Start API

```bash
uvicorn apps.api.main:app --reload
```

---

## Start Worker

```bash
python -m workers.ingestion.worker
```

---

## API

Swagger

```
http://127.0.0.1:8000/docs
```

POST

```
/upload
```

---

## Technologies

- FastAPI
- PostgreSQL
- MinIO
- Temporal
- Qdrant