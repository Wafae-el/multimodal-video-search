from datetime import timedelta

from temporalio import workflow

from packages.workflow.activities import (
    validate_asset,
    probe_video,
    normalize_video,
    extract_audio,
    generate_thumbnail,
)


@workflow.defn
class ProcessAssetWorkflow:

    @workflow.run
    async def run(self, asset: dict) -> str:

        asset = await workflow.execute_activity(
            validate_asset,
            asset,
            start_to_close_timeout=timedelta(seconds=30),
        )

        asset = await workflow.execute_activity(
            probe_video,
            asset,
            start_to_close_timeout=timedelta(seconds=30),
        )

        asset = await workflow.execute_activity(
            normalize_video,
            asset,
            start_to_close_timeout=timedelta(seconds=30),
        )

        asset = await workflow.execute_activity(
            extract_audio,
            asset,
            start_to_close_timeout=timedelta(seconds=30),
        )

        asset = await workflow.execute_activity(
            generate_thumbnail,
            asset,
            start_to_close_timeout=timedelta(seconds=30),
        )

        return asset["filename"]