# Weeks 2–5 Implementation Notes

This repository now includes small, production-oriented primitives for the next
four research-quest phases. They are intentionally dependency-light and testable
without external services, so they can later be wired into the durable Week 1
Temporal pipeline.

## Week 2: Segmentation and shared timestamps

`packages.segmentation.timeline` provides millisecond `Interval` values,
temporal IoU, gap-aware interval merging, and timeline coverage. Reversed and
negative timestamps are rejected so modality timelines cannot move backward.

## Week 3: Spoken-text hybrid retrieval

`packages.retrieval.scoring` provides L2 normalization, cosine similarity,
BM25-style lexical scoring, and reciprocal-rank fusion. Dense and sparse
retrievers stay independent until fusion, preserving exact-name and paraphrase
behavior.

## Week 4: Visual examples and frame memory

`packages.visual.memory` provides query-frame to archive-frame scoring with
max-plus-mean clip pooling, plus duplicate suppression so near-identical frames
collapse to one returned moment.

## Week 5: Audio quality and query-quality control

`packages.audio_quality.quality` provides a transparent audio quality heuristic and active
channel weight renormalization. Silence remains a valid explicit state with a
zero quality contribution rather than an exception.


## Workflow integration

The Temporal workflow now continues after thumbnail generation through four
idempotent activities: `segment_media`, `index_speech`, `index_visual`, and
`score_audio_quality`. In this repository they write deterministic JSON
manifests to object storage and register them as derived media files, preserving
the production contracts while model-serving components remain out of scope.

## Week 6: Fusion, reranking and temporal aggregation

`packages.fusion.ranking` provides quality-weighted reciprocal-rank fusion,
exact cosine reranking hooks, bounded support bonuses, and temporal grouping of
nearby multimodal candidates. Raw model scores are not added together; rank and
quality-normalized evidence is fused instead.

## Week 7: API contract and independent integration

`POST /v1/search` validates a typed multimodal query, rejects unsupported
modalities and invalid weights, renormalizes active modality weights, and returns
a stable `SearchResponse`. `GET /v1/search/{query_id}` exposes the saved result
for client contract tests. `POST /v1/reindex/{asset_id}` and
`DELETE /v1/assets/{asset_id}` expose stable integration points without hiding
unfinished business logic.

## Week 8: Evaluation and hardening

`packages.evaluation.metrics` provides precision@K, recall@K, MRR, nDCG and
temporal-IoU helpers for release reports. `packages.domain.interfaces` defines
protocols for visual/audio encoders, vector stores and fusion strategies so later
model adapters stay replaceable.
