from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from packages.workflow.activities import (
        probe_video,
        normalize_video,
        extract_audio,
        generate_thumbnail,
    )

@dataclass
class WorkflowInput:
    asset_id: str
    pipeline_version: str = "v1"

@dataclass
class WorkflowResult:
    asset_id: str
    status: str
    pipeline_version: str

ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=3,
)

@workflow.defn
class ProcessAssetWorkflow:
    @workflow.run
    async def run(self, request: WorkflowInput) -> WorkflowResult:
        asset = {
            "asset_id": request.asset_id,
            "pipeline_version": request.pipeline_version,
        }

        try:
            asset = await workflow.execute_activity(
                probe_video,
                asset,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=ACTIVITY_RETRY,
            )

            asset = await workflow.execute_activity(
                normalize_video,
                asset,
                start_to_close_timeout=timedelta(minutes=20),
                retry_policy=ACTIVITY_RETRY,
            )

            asset = await workflow.execute_activity(
                extract_audio,
                asset,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=ACTIVITY_RETRY,
            )

            asset = await workflow.execute_activity(
                generate_thumbnail,
                asset,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=ACTIVITY_RETRY,
            )

            return WorkflowResult(
                asset_id=request.asset_id,
                status="COMPLETED",
                pipeline_version=request.pipeline_version,
            )

        except Exception:
            return WorkflowResult(
                asset_id=request.asset_id,
                status="FAILED",
                pipeline_version=request.pipeline_version,
            )