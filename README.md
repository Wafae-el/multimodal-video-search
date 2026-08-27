# Multimodal Video Search

## Project Purpose

Multimodal Video Search is a backend platform for ingesting, processing, indexing and retrieving information from video content through multiple modalities:

* spoken text,
* audio/acoustic content,
* visual content,
* semantic embeddings,
* lexical search,
* multimodal fusion.

The project is designed as a production-oriented backend where each processing stage is time-aligned and independently searchable.

The system progressively transforms a raw video into:

1. validated media,
2. normalized video,
3. extracted audio,
4. temporal segments and representative frames,
5. ASR transcript segments,
6. sentence-aware transcript chunks,
7. audio windows and acoustic embeddings,
8. visual embeddings,
9. searchable Qdrant collections,
10. multimodal retrieval results.

---

# Project Architecture

The project is organized as a modular backend pipeline.

```text
                         ┌─────────────────────┐
                         │      Client/API     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      FastAPI        │
                         │   Upload / Status   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Temporal Workflow   │
                         │ Durable Processing  │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
       │    Video    │       │    Audio    │       │   Frames    │
       │ Processing  │       │ Processing  │       │ Processing  │
       └──────┬──────┘       └──────┬──────┘       └──────┬──────┘
              │                     │                     │
              ▼                     ▼                     ▼
       Scene / Frames          Whisper / CLAP          OpenCLIP
              │                     │                     │
              ▼                     ▼                     ▼
          Qdrant                  Qdrant                Qdrant
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Hybrid Retrieval    │
                         │ Dense + Sparse +    │
                         │ Multimodal Fusion   │
                         └─────────────────────┘
                                    │
                                    ▼
                              Search Results
```

---

# Project Progress

The project is divided into progressive implementation phases.

| Week   | Phase                                     | Status        |
| ------ | ----------------------------------------- | ------------- |
| Week 1 | Foundation and durable ingestion          | ✅ Implemented |
| Week 2 | Segmentation and media preprocessing      | ✅ Implemented |
| Week 3 | Spoken-text modality and hybrid retrieval | ✅ Implemented |
| Week 4 | Visual modality and image/video examples  | ✅ Implemented |
| Week 5 | Audio modality and query-quality control  | ✅ Implemented |

---

# Week 1 — Foundation and Durable Ingestion

## Scope

Week 1 establishes the production foundation of the platform.

Implemented components include:

* FastAPI upload API
* Pydantic request/response contracts
* ffprobe media validation
* PostgreSQL metadata persistence
* SQLAlchemy models
* Alembic migrations
* MinIO/S3-compatible object storage
* Temporal durable workflows
* retry-safe activities
* deterministic operation keys
* processing state machine
* worker restart recovery
* duplicate delivery protection
* explicit invalid-media states
* Docker Compose environment
* integration and unit tests

The original Week 1 README already documents these components in detail.

## Durable Processing

Every activity derives a deterministic operation key:

```text
operation_key =
SHA256(
    asset_checksum
    ||
    step
    ||
    step_version
    ||
    tool_version
)
```

A completed operation is reused instead of being executed again.

This guarantees that retries and duplicate deliveries do not create duplicate artifacts.

## Processing Pipeline

```text
UPLOAD
   │
   ▼
VALIDATING
   │
   ▼
PROBING
   │
   ▼
NORMALIZING
   │
   ▼
EXTRACTING_AUDIO
   │
   ▼
GENERATING_THUMBNAIL
   │
   ▼
DONE
```

The terminal failure states remain:

```text
FAILED
NO_AUDIO
```

as documented in the Week 1 implementation.

---

# Week 2 — Segmentation and Media Preprocessing

## Objective

Week 2 transforms the normalized media into **time-aligned units** that can later be consumed independently by text, audio and visual retrieval.

The main principle is that every generated artifact must preserve its temporal position in the original video.

---

## Temporal Representation

All temporal information is represented in milliseconds.

```text
start_ms
end_ms
duration_ms
```

This common representation allows:

* scene intervals,
* ASR intervals,
* audio windows,
* visual frames,
* transcript chunks

to be compared and fused using the same timeline.

---

## Audio Window Segmentation

Audio is divided into fixed-size overlapping windows.

The implemented configuration is:

```text
Window duration = 5 seconds
Overlap          = 2.5 seconds
Hop              = 2.5 seconds
```

The implementation uses:

```python
AudioWindowGenerator(
    window_ms=5000,
    overlap_ms=2500,
)
```

The generated windows follow:

```text
Window 0: 0      → 5000 ms
Window 1: 2500   → 7500 ms
Window 2: 5000   → 10000 ms
Window 3: 7500   → 12500 ms
...
```

This overlap prevents information from being lost at window boundaries.

---

## Audio Window Extraction

The project also contains an `AudioWindowExtractor` responsible for creating the actual audio files associated with the generated temporal windows.

The processing flow is:

```text
source.wav
    │
    ▼
AudioWindowExtractor
    │
    ├── window 0
    ├── window 1
    ├── window 2
    ├── ...
    └── window N
```

Each extracted window maintains its original:

```text
start_ms
end_ms
```

information.

---

## Timeline Alignment

The same temporal coordinates are used by different modalities.

```text
VIDEO
──────────────────────────────────────────────►

SCENE
───────████████──────████████──────██████─────

ASR
─────────████████████────████████─────────────

AUDIO
████████████████████████████████████████████─

FRAME
────●──────────●──────────●──────────●────────
```

This shared timeline is essential for multimodal fusion in later phases.

---

## Week 2 Validation

The audio segmentation pipeline was tested on the indexed video.

For the tested asset:

```text
Duration       = 364112 ms
                ≈ 364 seconds

Audio windows  = 145

Window size    = 5000 ms
Overlap        = 2500 ms
```

The generated number of windows confirms that the temporal segmentation is operational.

---

# Week 3 — Spoken-Text Modality and Hybrid Retrieval

## Objective

Week 3 introduces spoken-language understanding.

The processing chain is:

```text
audio
  │
  ▼
Faster-Whisper
  │
  ▼
ASR segments
  │
  ▼
normalized transcript
  │
  ▼
sentence-aware chunks
  │
  ├───────────────┐
  ▼               ▼
Dense Search    Sparse Search
  │               │
  └───────┬───────┘
          ▼
       RRF Fusion
          │
          ▼
      Text Results
```

---

## Automatic Speech Recognition

The project uses Faster-Whisper through the `WhisperService`.

```python
WhisperModel(
    model_size="small",
    device="cpu",
    compute_type="int8",
)
```

The service returns temporal transcript segments containing:

```text
start_ms
end_ms
text
confidence
language
```

---

## ASR Confidence

Whisper's `avg_logprob` is converted into a normalized confidence value.

The current implementation applies:

```python
confidence = exp(avg_logprob)
```

followed by clipping:

```text
0 ≤ confidence ≤ 1
```

Therefore ASR confidence can be used directly by the audio-quality model.

---

## Transcript Preservation

The system preserves the original transcript while also producing normalized text.

The transcript processing therefore keeps:

```text
raw text
normalized text
language
confidence
source segment IDs
start_ms
end_ms
```

Normalization does not replace the original ASR evidence.

---

## Sentence-Aware Chunking

Whisper segments are grouped into larger semantic chunks.

The resulting speech chunks contain:

```text
chunk_id
video_id
start_ms
end_ms
text
normalized_text
source_segment_ids
confidence
language
```

Example:

```text
speech-000006
```

with a temporal interval such as:

```text
105530 ms → 126450 ms
```

This allows retrieval results to point back to an exact section of the video.

---

## Dense Retrieval

Dense retrieval uses semantic embeddings.

The goal is to retrieve semantically related content even when the query does not exactly match the transcript wording.

For example:

```text
Query:
"learning algorithms"

Possible transcript:
"machine learning methods"
```

A dense semantic encoder can recognize the relationship.

---

## Sparse Retrieval

Sparse retrieval is implemented using BM25.

It is particularly useful for:

* proper names,
* exact terminology,
* acronyms,
* numbers,
* technical expressions,
* exact phrases.

The system restores the BM25 index at startup.

Example observed during validation:

```text
BM25 restored: 21 chunks
```

---

## Reciprocal Rank Fusion

Dense and sparse retrieval are combined using Reciprocal Rank Fusion.

The basic formula is:

```text
RRF(d) = Σ 1 / (k + rank(d))
```

with:

```text
k = 60
```

The fusion does not assume that dense and sparse scores are directly comparable.

Instead, it combines their **rank positions**.

---

## Week 3 Validation

The retrieval system was tested using:

```text
machine learning
cross-validation
logistic regression
```

### Query: machine learning

The system returned highly relevant speech chunks including:

```text
speech-000006
speech-000007
speech-000008
```

For example, `speech-000006` covers:

```text
105530 → 126450 ms
```

and contains discussion of:

```text
machine learning
training the algorithm
evaluating machine learning methods
testing the algorithm
```

### Query: cross-validation

The system returned:

```text
speech-000018
speech-000017
speech-000013
speech-000004
```

### Query: logistic regression

The system returned:

```text
speech-000019
speech-000005
speech-000002
```

These tests demonstrate that the spoken-content retrieval pipeline is operational.

---

# Week 4 — Visual Modality and Image/Video Examples

## Objective

Week 4 introduces visual retrieval.

The objective is to search for visual information even when it is:

* never spoken,
* not present in the transcript,
* not explicitly tagged.

The visual processing pipeline is:

```text
Video
  │
  ▼
Scene / Representative Frames
  │
  ▼
Image Preprocessing
  │
  ▼
OpenCLIP
  │
  ▼
Visual Embeddings
  │
  ▼
Qdrant
  │
  ▼
Visual Search
```

---

## Visual Encoder

The project uses an OpenCLIP-based visual encoder.

The visual embeddings are associated with metadata such as:

```text
video_id
scene_id
timestamp_ms
object_key
embedding_model
embedding_provider
embedding_version
modality
```

The validated results show:

```text
embedding_model = ViT-B-32
embedding_provider = openai
embedding_version = openclip-vit-b32-v1
```

---

## Text-to-Frame Search

A textual query can be compared against visual frame embeddings.

Conceptually:

```text
S_visual(q, i)
=
cos(
    E_text(q),
    E_image(frame_i)
)
```

This makes it possible to search visual content using a textual description.

---

## Image-to-Frame Search

The same visual embedding space can also support image-based queries.

```text
Query Image
     │
     ▼
OpenCLIP
     │
     ▼
Query Embedding
     │
     ▼
Cosine Similarity
     │
     ▼
Matching Frames
```

This allows a single visual collection to support both:

```text
text → frame
image → frame
```

---

## Duplicate Frame Handling

Near-identical frames should not flood the retrieval results.

The visual pipeline therefore considers:

* similarity,
* duplicate frames,
* representative frames,
* scene-level selection.

The objective is to return representative visual evidence instead of many nearly identical frames.

---

## Visual Retrieval Results

The validated multimodal search produced visual candidates containing:

```text
video_id
scene_id
timestamp_ms
object_key
```

For example, one visual result returned:

```text
video_id = 12
scene_id = 6
timestamp_ms = 310026
```

Another visual candidate returned:

```text
video_id = 12
timestamp_ms = 127994
```

These timestamps allow the frontend or API consumer to locate the exact visual moment in the video.

---

# Week 5 — Audio Modality and Query-Quality Control

## Objective

Week 5 introduces the dedicated audio modality.

The important distinction is between:

### Speech content

> What was said?

and:

### Acoustic content

> What does the sound resemble?

For example:

```text
Speech:
"machine learning"

Acoustic:
applause
music
crowd
siren
noise
silence
```

The two channels are therefore kept separate until multimodal fusion.

---

# Audio Processing Architecture

```text
                         Audio
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
       Speech Analysis              Acoustic Analysis
             │                           │
             ▼                           ▼
       Faster-Whisper                    CLAP
             │                           │
             ▼                           ▼
       ASR confidence              Audio embedding
       speech ratio                     │
             │                           │
             └─────────────┬─────────────┘
                           ▼
                    Audio Quality
                           │
                           ▼
                    Quality-aware
                     Audio Search
```

---

# Audio Windows

Audio search uses:

```text
5-second windows
2.5-second overlap
```

This was validated on the project video.

For the tested 364-second audio:

```text
145 windows
```

were generated.

---

# ASR-to-Window Alignment

Whisper transcript segments are mapped onto audio windows according to their temporal overlap.

For every window:

```text
window.start_ms
window.end_ms
```

is compared with:

```text
segment.start_ms
segment.end_ms
```

The overlap is calculated as:

```text
overlap_start =
max(window.start_ms, segment.start_ms)

overlap_end =
min(window.end_ms, segment.end_ms)
```

Only positive temporal overlaps contribute.

---

# Speech Ratio

The system calculates the proportion of a window associated with speech.

At the window level:

```text
speech_ratio =
total temporal speech overlap
/
window duration
```

The value is bounded to:

```text
0 ≤ speech_ratio ≤ 1
```

This allows silent and speech-heavy windows to be distinguished.

---

# ASR Confidence per Audio Window

If several Whisper segments overlap a window, their confidence values are weighted by temporal overlap.

```text
ASR_confidence =
Σ(segment_confidence × overlap_ms)
/
Σ(overlap_ms)
```

This produces one confidence value for every audio window.

---

# Audio Quality Analysis

The `AudioQualityAnalyzer` computes the following signals:

```text
speech_ratio
clipping_ratio
loudness
snr_proxy
snr_norm
asr_confidence
quality
```

---

## Clipping Ratio

Clipping is detected when:

```text
abs(sample) >= 0.98
```

The clipping ratio is:

```text
clipped samples
/
total samples
```

A high clipping ratio reduces the final audio quality.

---

## Loudness

Loudness is estimated using normalized RMS:

```text
RMS =
sqrt(
    mean(samples²)
)
```

The resulting value is clipped to:

```text
0 → 1
```

---

## SNR Proxy

The project uses a transparent SNR proxy rather than a calibrated acoustic SNR meter.

Samples are divided into:

```text
active signal
low-energy noise
```

Then:

```text
SNR =
10 × log10(signal_power / noise_power)
```

The result is bounded between:

```text
-60 dB
+
60 dB
```

---

## SNR Normalization

The SNR proxy is mapped into `[0,1]`.

Using:

```text
minimum = -20 dB
maximum = 40 dB
```

the normalization is:

```text
SNR_norm =
(SNR - minimum)
/
(maximum - minimum)
```

followed by clipping to:

```text
[0,1]
```

---

# Audio Quality Score

The implemented audio-quality equation is:

```text
q_audio =
clip(
    w1 × SNR_norm
    +
    w2 × speech_ratio
    +
    w3 × ASR_confidence
    -
    w4 × clipping_ratio,
    0,
    1
)
```

Default weights:

```text
w1 = 0.35
w2 = 0.25
w3 = 0.25
w4 = 0.15
```

Therefore:

```text
q_audio =
0.35 × SNR_norm
+
0.25 × speech_ratio
+
0.25 × ASR_confidence
-
0.15 × clipping_ratio
```

The final score is always:

```text
0 ≤ q_audio ≤ 1
```

---

# Audio Quality Stored in Qdrant

Each audio window indexed in Qdrant stores quality-related metadata.

Example payload:

```json
{
  "video_id": 12,
  "start_ms": 127500,
  "end_ms": 132500,
  "embedding_model": "CLAP",
  "embedding_provider": "laion",
  "embedding_version": "clap-htsat-unfused",
  "modality": "audio",
  "speech_ratio": 0.5511,
  "clipping_ratio": 0.0,
  "loudness": 0.0879,
  "snr_proxy": 30.66,
  "snr_norm": 0.8444,
  "asr_confidence": 0.8995,
  "quality_score": 0.6582
}
```

This makes audio quality transparent and inspectable.

---

# CLAP Acoustic Embeddings

The project uses CLAP for acoustic similarity.

The embedding configuration validated in the system is:

```text
embedding_model:
CLAP

embedding_provider:
laion

embedding_version:
clap-htsat-unfused
```

The embeddings are stored in the Qdrant collection:

```text
video_audio_windows
```

using cosine distance.

---

# Audio Qdrant Collection

The audio vector store uses:

```text
Collection:
video_audio_windows

Vector size:
512

Distance:
COSINE
```

Each vector has a deterministic point ID based on:

```text
video_id
start_ms
end_ms
```

Conceptually:

```text
point_id =
UUID5(
    "video={video_id}:"
    "start={start_ms}:"
    "end={end_ms}"
)
```

This prevents duplicate audio windows when the same processing operation is repeated.

---

# Audio Search

Audio search returns dense candidates containing:

```text
point_id
score
rank
payload
```

The payload contains temporal and quality information.

The raw audio retrieval results are then aggregated before multimodal fusion.

---

# Neighboring Audio Aggregation

Several neighboring audio windows can belong to the same acoustic event.

Instead of returning every individual 5-second window, neighboring hits are aggregated.

An aggregated result contains:

```text
result_id
score
start_ms
end_ms
quality_score
window_count
audio_ranks
payload
```

For example, the validated search produced an aggregated result:

```text
start_ms     = 2500
end_ms       = 25000
window_count = 8
quality      ≈ 0.79
```

This reduces duplicated neighboring results.

---

# Silence Handling

Silence is treated as a valid state.

A silent audio window must not cause the entire multimodal result to disappear.

Instead:

```text
audio contribution → reduced / absent
text contribution  → preserved
visual contribution → preserved
```

This is important because a video may contain:

* speech followed by silence,
* visual information without speech,
* acoustic information without speech.

---

# Multimodal Retrieval

The final retrieval system combines:

```text
TEXT
AUDIO
VISUAL
```

The architecture is:

```text
                 Query
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
      Text       Audio      Visual
        │          │          │
        ▼          ▼          ▼
     Dense +     CLAP       OpenCLIP
     BM25          │          │
        │          │          │
        └──────────┼──────────┘
                   ▼
          Temporal Matching
                   │
                   ▼
          Quality-aware Fusion
                   │
                   ▼
          Multimodal Results
```

---

# Reciprocal Rank Fusion

The multimodal fusion combines the rank of each candidate from:

```text
text
audio
visual
```

using RRF.

Each modality contributes:

```text
1 / (k + rank)
```

to the final score.

The implementation keeps independent ranks:

```text
text_rank
audio_rank
visual_rank
```

A result can therefore be:

```text
TEXT = 2
AUDIO = 2
VISUAL = 1
```

which indicates that the same temporal content is supported by all three modalities.

---

# Temporal Multimodal Fusion

The system does not simply combine unrelated text, audio and visual candidates.

It also checks temporal proximity.

For speech chunks:

```text
chunk.start_ms
chunk.end_ms
```

are compared against audio windows and visual timestamps.

This allows the system to associate:

```text
spoken content
+
corresponding sound
+
corresponding visual frame
```

from the same part of the video.

---

# Multimodal Evidence

The resulting payload can contain:

```text
temporal_fusion
matched_audio_count
matched_visual_count
audio_evidence
visual_evidence
```

For example:

```json
{
  "temporal_fusion": true,
  "matched_audio_count": 1,
  "matched_visual_count": 1,
  "audio_evidence": [
    {
      "rank": 2,
      "start_ms": 120000,
      "end_ms": 127500,
      "quality_score": 0.6701
    }
  ],
  "visual_evidence": [
    {
      "rank": 1,
      "timestamp_ms": 127994
    }
  ]
}
```

This provides explicit evidence for why a multimodal result was returned.

---

# Quality-Aware Modality Weights

The fusion system assigns modality weights.

The validated results contain weights such as:

```text
text   ≈ 0.364
audio  ≈ 0.271
visual ≈ 0.364
```

Audio quality is used as a modality-quality signal.

For example:

```text
modality_quality:
{
    "text": 1.0,
    "audio": 0.7446,
    "visual": 1.0
}
```

The principle is:

```text
better quality
      ↓
higher modality contribution

poor quality
      ↓
reduced modality contribution
```

Only active modalities should participate in the final normalization.

---

# End-to-End Retrieval Example

For:

```text
machine learning
```

the validated system returned:

```text
TEXT RESULTS     = 5
RAW AUDIO        = 15
AGGREGATED AUDIO = 5
VISUAL RESULTS   = 3
MULTIMODAL       = 5
```

The highest multimodal result was:

```text
ID       = speech-000006
TEXT     = 2
AUDIO    = 2
VISUAL   = 1
VIDEO    = 12
START    = 105530
END      = 126450
```

This is a strong multimodal match because the same result is supported by:

```text
text rank 2
audio rank 2
visual rank 1
```

---

# Query Validation

The system was tested with several representative queries.

## Machine Learning

```text
machine learning
```

Results included speech chunks discussing:

* machine learning methods,
* training,
* testing,
* evaluating algorithms.

The highest results received simultaneous text/audio/visual evidence.

---

## Cross Validation

```text
cross-validation
```

Results included:

```text
speech-000018
speech-000017
speech-000013
speech-000004
```

The top result had:

```text
TEXT   = 5
AUDIO  = 5
VISUAL = 1
```

---

## Logistic Regression

```text
logistic regression
```

Results included:

```text
speech-000019
speech-000005
speech-000002
```

The retrieved chunks contain direct references to logistic regression and machine-learning methodology.

---

# Qdrant Collections

The project now uses Qdrant for vector-based retrieval.

The audio collection is:

```text
video_audio_windows
```

Visual embeddings are stored with metadata including:

```text
video_id
scene_id
timestamp_ms
object_key
embedding_model
embedding_provider
embedding_version
modality
```

Audio embeddings additionally store:

```text
speech_ratio
clipping_ratio
loudness
snr_proxy
snr_norm
asr_confidence
quality_score
```

---

# Repository Structure

```text
apps/
└── api/
    └── FastAPI application

workers/
└── ingestion/
    └── Temporal worker

packages/
├── audio/
│   ├── quality.py
│   ├── speech_windows.py
│   ├── windowing.py
│   └── window_extractor.py
│
├── speech/
│   ├── whisper_service.py
│   ├── chunker.py
│   └── normalizer.py
│
├── retrieval/
│   ├── fusion.py
│   ├── service.py
│   ├── bm25.py
│   ├── qdrant_store.py
│   └── audio_qdrant_store.py
│
├── workflow/
│   ├── activities.py
│   ├── workflows.py
│   └── contracts.py
│
├── media/
│   ├── ffprobe validation
│   ├── normalization
│   └── thumbnail generation
│
└── storage/
    └── MinIO/S3 integration
```

---

# Technologies

## Backend

```text
Python 3.12
FastAPI
Pydantic
SQLAlchemy
Alembic
```

## Workflow

```text
Temporal
Temporal Python SDK
```

## Storage

```text
PostgreSQL
MinIO
S3-compatible object storage
```

## Vector Database

```text
Qdrant
```

## Speech

```text
Faster-Whisper
```

## Audio Embeddings

```text
CLAP
```

## Visual Embeddings

```text
OpenCLIP
```

## Search

```text
BM25
Dense semantic retrieval
Reciprocal Rank Fusion
Multimodal fusion
```

## Media Processing

```text
FFmpeg
ffprobe
librosa
```

## Infrastructure

```text
Docker
Docker Compose
```

---

# Docker Environment

The complete development environment is reproducible through Docker Compose.

Main services include:

```text
API
Worker
PostgreSQL
MinIO
Temporal
Qdrant
```

The Week 1 setup already documents the standard Compose startup command.

```bash
docker compose -f infrastructure/docker-compose.yml up -d
```

---

# Running the Worker

```bash
python -m workers.ingestion.worker
```

The worker executes Temporal activities and handles long-running media-processing operations through the configured activity thread pool.

---

# Validation Commands

## Python Compilation

```bash
python -m py_compile packages/workflow/activities.py
```

Docker validation:

```bash
docker exec video_worker \
python -m py_compile \
/app/packages/workflow/activities.py
```

---

## Audio Analyzer Validation

```bash
docker exec video_worker python -c \
"from packages.audio.speech_windows import AudioSpeechWindowAnalyzer;
print('SPEECH WINDOW ANALYZER = OK')"
```

Expected:

```text
SPEECH WINDOW ANALYZER = OK
```

---

## Audio Indexing

The audio indexing activity can be executed using the asset identifier.

The validated execution produced:

```text
indexed audio windows = 145
```

with quality information stored in Qdrant.

---

## Retrieval Validation

Example:

```bash
docker exec video_worker python -c "..."
```

The retrieval service was validated for:

```text
machine learning
cross-validation
logistic regression
```

with successful multimodal results.

---

# Current End-to-End Pipeline

The current implementation can be summarized as:

```text
                    VIDEO UPLOAD
                         │
                         ▼
                Week 1 Ingestion
                         │
                         ▼
                 Normalized Video
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
           Scenes      Audio      Thumbnail
              │          │
              ▼          ▼
           Frames     5s Windows
              │          │
              ▼          ▼
          OpenCLIP    Whisper
              │          │
              │          ▼
              │      Transcript
              │          │
              │          ▼
              │      Text Chunks
              │          │
              │     ┌────┴────┐
              │     ▼         ▼
              │   Dense      BM25
              │     │         │
              │     └────┬────┘
              │          ▼
              │         RRF
              │
              ▼
          Visual Search

                         Audio
                           │
                           ▼
                          CLAP
                           │
                           ▼
                     Audio Search
                           │
                           ▼
                    Quality Control
                           │
                           └──────────────┐
                                          ▼
                              Multimodal Fusion
                                          │
                                          ▼
                                  Final Search Results
```

---

# Current Validation Status

The Weeks 2 → 5 implementation has been exercised against a real indexed video.

Validated components include:

```text
✅ 5-second audio windows
✅ 2.5-second audio overlap
✅ Whisper ASR
✅ ASR temporal segments
✅ ASR confidence normalization
✅ Speech-to-window alignment
✅ Speech ratio
✅ Audio clipping ratio
✅ Loudness
✅ SNR proxy
✅ SNR normalization
✅ Audio quality score
✅ CLAP audio embeddings
✅ Qdrant audio indexing
✅ Audio neighboring-window aggregation
✅ BM25 retrieval
✅ Dense retrieval
✅ RRF fusion
✅ OpenCLIP visual retrieval
✅ Temporal multimodal matching
✅ Audio evidence in multimodal results
✅ Visual evidence in multimodal results
✅ Quality-aware multimodal fusion
```

---

# Example of Indexed Audio Quality

A validated audio window produced values such as:

```text
speech_ratio      = 0.5511
clipping_ratio    = 0.0
loudness          = 0.0879
snr_proxy         = 30.66 dB
snr_norm          = 0.8444
asr_confidence    = 0.8995
quality_score     = 0.6582
```

Another window produced:

```text
speech_ratio      = 0.6428
clipping_ratio    = 0.0
loudness          = 0.0808
snr_proxy         = 27.65 dB
snr_norm          = 0.7942
asr_confidence    = 0.9002
quality_score     = 0.6637
```

These values demonstrate that the quality signals are not merely theoretical: they are actually calculated and persisted with the indexed audio windows.

---

# Known Limitations

## Qdrant Version Warning

The current Docker environment reports:

```text
Qdrant client = 1.19.0
Qdrant server = 1.13.4
```

The client warns that the versions are not fully compatible.

The current pipeline nevertheless executes successfully.

---

## Hugging Face Authentication

Model loading currently reports:

```text
You are sending unauthenticated requests to the HF Hub.
```

The models load successfully, but configuring `HF_TOKEN` would improve download limits and performance.

---

## CPU Inference

The current configuration uses:

```text
Whisper → CPU / int8
CLAP    → CPU
```

This is appropriate for reproducible local development but can be optimized for GPU deployment.

---

# Week 5 Completion

The Week 5 objective is now covered by the implemented audio pipeline:

```text
Audio
  │
  ├── Speech content
  │       └── Whisper → transcript retrieval
  │
  └── Acoustic similarity
          └── CLAP → acoustic retrieval

        +

Speech ratio
Clipping ratio
Loudness
SNR proxy
ASR confidence
        │
        ▼
Audio Quality Score
        │
        ▼
Quality-aware Multimodal Fusion
```

The system therefore distinguishes between:

```text
"what was said"
```

and:

```text
"what the sound resembles"
```

while allowing audio quality to influence the final multimodal contribution.

---

# Overall Project Status

```text
Week 1 ─ Foundation
        ✅ Durable ingestion
        ✅ PostgreSQL
        ✅ MinIO
        ✅ Temporal
        ✅ Idempotency

Week 2 ─ Segmentation
        ✅ Temporal windows
        ✅ Audio extraction
        ✅ Shared timestamps

Week 3 ─ Spoken Text
        ✅ Faster-Whisper
        ✅ Transcript chunks
        ✅ Dense retrieval
        ✅ BM25
        ✅ RRF

Week 4 ─ Visual
        ✅ OpenCLIP
        ✅ Visual embeddings
        ✅ Text-to-frame retrieval
        ✅ Visual timestamps
        ✅ Duplicate-aware retrieval

Week 5 ─ Audio
        ✅ 5s / 2.5s windows
        ✅ Speech alignment
        ✅ CLAP
        ✅ Audio quality
        ✅ SNR proxy
        ✅ ASR confidence
        ✅ Quality-aware fusion
        ✅ Multimodal temporal fusion
```

## Current milestone

**Weeks 1–5 implemented and validated on the local Docker stack.**
