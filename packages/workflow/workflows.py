from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from packages.workflow.contracts import (
    ProcessAssetInput,
    WorkflowResult,
    ACTIVITY_MAX_ATTEMPTS,
)

with workflow.unsafe.imports_passed_through():
    from packages.workflow.activities import (
        probe_video,
        normalize_video,
        extract_audio,
        generate_thumbnail,
        segment_media,
        index_speech,
        index_visual,
        score_audio_quality,
    )

# Explicit retry policy: bounded attempts, exponential backoff, and media
# validation errors marked non-retryable so corrupt/unsupported media fails fast.
ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=ACTIVITY_MAX_ATTEMPTS,
    non_retryable_error_types=["MediaValidationError"],
)


@workflow.defn
class ProcessAssetWorkflow:
    @workflow.run
    async def run(self, request: ProcessAssetInput) -> WorkflowResult:
        # Sequence: probe -> normalize -> extract audio -> generate thumbnail.
        # Each activity reads/writes state from the database and is idempotent,
        # so only stable identifiers travel through Temporal history.
        # heartbeat_timeout lets Temporal detect a dead/killed worker within
        # seconds (instead of waiting for start_to_close_timeout) and reschedule
        # the idempotent activity.
        heartbeat = timedelta(seconds=10)
        try:
            await workflow.execute_activity(
                probe_video,
                request,
                start_to_close_timeout=timedelta(minutes=2),
                heartbeat_timeout=heartbeat,
                retry_policy=ACTIVITY_RETRY,
            )
            await workflow.execute_activity(
                normalize_video,
                request,
                start_to_close_timeout=timedelta(minutes=20),
                heartbeat_timeout=heartbeat,
                retry_policy=ACTIVITY_RETRY,
            )
            await workflow.execute_activity(
                extract_audio,
                request,
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=heartbeat,
                retry_policy=ACTIVITY_RETRY,
            )
            await workflow.execute_activity(
                generate_thumbnail,
                request,
                start_to_close_timeout=timedelta(minutes=5),
                heartbeat_timeout=heartbeat,
                retry_policy=ACTIVITY_RETRY,
            )
            await workflow.execute_activity(
                segment_media,
                request,
                start_to_close_timeout=timedelta(minutes=2),
                heartbeat_timeout=heartbeat,
                retry_policy=ACTIVITY_RETRY,
            )
            await workflow.execute_activity(
                index_speech,
                request,
                start_to_close_timeout=timedelta(minutes=2),
                heartbeat_timeout=heartbeat,
                retry_policy=ACTIVITY_RETRY,
            )
            await workflow.execute_activity(
                index_visual,
                request,
                start_to_close_timeout=timedelta(minutes=2),
                heartbeat_timeout=heartbeat,
                retry_policy=ACTIVITY_RETRY,
            )
            await workflow.execute_activity(
                score_audio_quality,
                request,
                start_to_close_timeout=timedelta(minutes=2),
                heartbeat_timeout=heartbeat,
                retry_policy=ACTIVITY_RETRY,
            )

            return WorkflowResult(
                asset_id=request.asset_id,
                status="COMPLETED",
                pipeline_version=request.pipeline_version,
            )

        except Exception:
            # The failing activity has already persisted the explicit failure
            # state on the asset (FAILED with last_error).
            return WorkflowResult(
                asset_id=request.asset_id,
                status="FAILED",
                pipeline_version=request.pipeline_version,
            )
