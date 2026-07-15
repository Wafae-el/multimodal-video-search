import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from packages.workflow.activities import (
    validate_asset,
    probe_video,
    normalize_video,
    detect_scenes_activity,
    extract_frames_activity,
    extract_audio,
    generate_thumbnail,
)

from packages.workflow.workflows import ProcessAssetWorkflow


async def main():

    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="video-processing",
        workflows=[ProcessAssetWorkflow],
        activities=[
             validate_asset,
             probe_video,
             normalize_video,
             detect_scenes_activity,
             extract_frames_activity,
             extract_audio,
             generate_thumbnail,
        ],
    )

    print("Temporal Worker started...")

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())