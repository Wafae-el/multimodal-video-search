from enum import Enum


class ProcessingState(Enum):
    WAITING_UPLOAD = "WAITING_UPLOAD"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProcessingEvent(Enum):
    UPLOAD_COMPLETE = "upload_complete"
    WORKER_CRASH = "worker_crash"
    RETRY = "retry"
    DUPLICATE_DELIVERY = "duplicate_delivery"
    OUTPUT_EXISTS = "output_exists"

def next_state(
    state: ProcessingState,
    event: ProcessingEvent,
) -> ProcessingState:
    """
    Pure state transition function.
    """

    transitions = {

        (
            ProcessingState.WAITING_UPLOAD,
            ProcessingEvent.UPLOAD_COMPLETE,
        ): ProcessingState.PROCESSING,

        (
            ProcessingState.PROCESSING,
            ProcessingEvent.WORKER_CRASH,
        ): ProcessingState.FAILED,

        (
            ProcessingState.FAILED,
            ProcessingEvent.RETRY,
        ): ProcessingState.PROCESSING,

        (
            ProcessingState.PROCESSING,
            ProcessingEvent.OUTPUT_EXISTS,
        ): ProcessingState.COMPLETED,

        (
            ProcessingState.COMPLETED,
            ProcessingEvent.DUPLICATE_DELIVERY,
        ): ProcessingState.COMPLETED,
    }

    return transitions.get(
        (state, event),
        state,
    )