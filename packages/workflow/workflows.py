from datetime import timedelta

from temporalio import workflow

from packages.workflow.activities import validate_asset


@workflow.defn
class ProcessAssetWorkflow:

    @workflow.run
    async def run(self, filename: str) -> str:
        result = await workflow.execute_activity(
            validate_asset,
            filename,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result