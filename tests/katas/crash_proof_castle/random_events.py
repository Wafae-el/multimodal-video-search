import random

from state_machine import (
    ProcessingState,
    ProcessingEvent,
    next_state,
)

EVENTS = [
    ProcessingEvent.UPLOAD_COMPLETE,
    ProcessingEvent.WORKER_CRASH,
    ProcessingEvent.RETRY,
    ProcessingEvent.DUPLICATE_DELIVERY,
    ProcessingEvent.OUTPUT_EXISTS,
]


def run_random_sequence(length: int = 20):

    state = ProcessingState.WAITING_UPLOAD

    final_artifacts = 0

    for _ in range(length):

        event = random.choice(EVENTS)

        previous_state = state

        state = next_state(state, event)

        if (
            previous_state != ProcessingState.COMPLETED
            and state == ProcessingState.COMPLETED
        ):
            final_artifacts += 1

    return state, final_artifacts