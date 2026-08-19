import asyncio
import logging
import signal
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

from packages.config.settings import settings
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
from packages.workflow.workflows import ProcessAssetWorkflow

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("worker")


async def main() -> None:
    client = await Client.connect(settings.TEMPORAL_ADDRESS)

    interrupt = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, interrupt.set)
        except NotImplementedError:
            # add_signal_handler is unavailable on Windows; KeyboardInterrupt
            # (handled in __main__) covers SIGINT there.
            pass

    # Synchronous (blocking) activities run on this thread pool so a long FFmpeg
    # job never blocks the Temporal event loop. The pool size and the max number
    # of concurrent activities are kept in sync to avoid starvation.
    with ThreadPoolExecutor(
        max_workers=settings.WORKER_ACTIVITY_THREADS,
        thread_name_prefix="activity",
    ) as executor:
        worker = Worker(
            client,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            workflows=[ProcessAssetWorkflow],
            activities=[
                probe_video,
                normalize_video,
                extract_audio,
                generate_thumbnail,
                segment_media,
                index_speech,
                index_visual,
                score_audio_quality,
            ],
            activity_executor=executor,
            max_concurrent_activities=settings.WORKER_ACTIVITY_THREADS,
            graceful_shutdown_timeout=timedelta(seconds=settings.WORKER_GRACEFUL_SHUTDOWN_SECONDS),
        )

        logger.info(
            "Temporal worker started on task queue '%s' (%d activity threads)",
            settings.TEMPORAL_TASK_QUEUE,
            settings.WORKER_ACTIVITY_THREADS,
        )

        # Run until interrupted; leaving the context manager drains in-flight
        # activities within the graceful shutdown timeout.
        async with worker:
            await interrupt.wait()
        logger.info("Worker shut down gracefully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
