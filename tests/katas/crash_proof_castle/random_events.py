import random

from packages.workflow.state_machine import (
    ProcessingState,
    ProcessingEvent,
    next_state,
)

EVENTS = [
    ProcessingEvent.UPLOAD_COMPLETE,
    ProcessingEvent.VALIDATION_OK,
    ProcessingEvent.PROBE_OK,
    ProcessingEvent.NORMALIZE_OK,
    ProcessingEvent.AUDIO_OK,
    ProcessingEvent.THUMBNAIL_OK,
    ProcessingEvent.SEGMENT_OK,
    ProcessingEvent.SPEECH_INDEX_OK,
    ProcessingEvent.VISUAL_INDEX_OK,
    ProcessingEvent.AUDIO_SCORE_OK,
    ProcessingEvent.ERROR,
]


VALID_TRANSITIONS = {
    (ProcessingState.UPLOADED, ProcessingEvent.UPLOAD_COMPLETE),
    (ProcessingState.VALIDATING, ProcessingEvent.VALIDATION_OK),
    (ProcessingState.VALIDATING, ProcessingEvent.NO_AUDIO),
    (ProcessingState.PROBING, ProcessingEvent.PROBE_OK),
    (ProcessingState.PROBING, ProcessingEvent.ERROR),
    (ProcessingState.NORMALIZING, ProcessingEvent.NORMALIZE_OK),
    (ProcessingState.NORMALIZING, ProcessingEvent.ERROR),
    (ProcessingState.EXTRACTING_AUDIO, ProcessingEvent.AUDIO_OK),
    (ProcessingState.EXTRACTING_AUDIO, ProcessingEvent.ERROR),
    (ProcessingState.GENERATING_THUMBNAIL, ProcessingEvent.THUMBNAIL_OK),
    (ProcessingState.GENERATING_THUMBNAIL, ProcessingEvent.ERROR),
    (ProcessingState.SEGMENTING, ProcessingEvent.SEGMENT_OK),
    (ProcessingState.SEGMENTING, ProcessingEvent.ERROR),
    (ProcessingState.INDEXING_SPEECH, ProcessingEvent.SPEECH_INDEX_OK),
    (ProcessingState.INDEXING_SPEECH, ProcessingEvent.ERROR),
    (ProcessingState.INDEXING_VISUAL, ProcessingEvent.VISUAL_INDEX_OK),
    (ProcessingState.INDEXING_VISUAL, ProcessingEvent.ERROR),
    (ProcessingState.SCORING_AUDIO, ProcessingEvent.AUDIO_SCORE_OK),
    (ProcessingState.SCORING_AUDIO, ProcessingEvent.ERROR),
}


def run_random_sequence(length: int = 20, seed: int = 42):
    rng = random.Random(seed)

    state = ProcessingState.UPLOADED
    artifact_created = False

    for _ in range(length):
        valid_events = [event for event in EVENTS if (state, event) in VALID_TRANSITIONS]

        if not valid_events:
            break

        event = rng.choice(valid_events)
        state = next_state(state, event)

        if state == ProcessingState.DONE and not artifact_created:
            artifact_created = True

    return state, int(artifact_created)
