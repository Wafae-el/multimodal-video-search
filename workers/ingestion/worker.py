import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from packages.config.settings import settings

from packages.workflow.activities import (
    probe_video,
    normalize_video,
    extract_audio,
    generate_thumbnail,
)

from packages.workflow.workflows import (
    ProcessAssetWorkflow,
)


async def main():

    client = await Client.connect(
        settings.TEMPORAL_ADDRESS,
    )

    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,

        workflows=[
            ProcessAssetWorkflow,
        ],

        activities=[
            probe_video,
            normalize_video,
            extract_audio,
            generate_thumbnail,
        ],
    )

    print(
        f"Temporal Worker started on "
        f"{settings.TEMPORAL_TASK_QUEUE}"
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())