from enum import Enum


class ProcessingState(str, Enum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    PROBING = "PROBING"
    NORMALIZING = "NORMALIZING"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    GENERATING_THUMBNAIL = "GENERATING_THUMBNAIL"
    DONE = "DONE"
    FAILED = "FAILED"
    NO_AUDIO = "NO_AUDIO"


class ProcessingEvent(str, Enum):
    UPLOAD_COMPLETE = "UPLOAD_COMPLETE"
    VALIDATION_OK = "VALIDATION_OK"
    PROBE_OK = "PROBE_OK"
    NORMALIZE_OK = "NORMALIZE_OK"
    AUDIO_OK = "AUDIO_OK"
    THUMBNAIL_OK = "THUMBNAIL_OK"
    ERROR = "ERROR"
    
def next_state(state: ProcessingState, event: ProcessingEvent) -> ProcessingState:

    transitions = {

        (ProcessingState.UPLOADED, ProcessingEvent.UPLOAD_COMPLETE):
            ProcessingState.VALIDATING,

        (ProcessingState.VALIDATING, ProcessingEvent.VALIDATION_OK):
            ProcessingState.PROBING,

        (ProcessingState.PROBING, ProcessingEvent.PROBE_OK):
            ProcessingState.NORMALIZING,

        (ProcessingState.NORMALIZING, ProcessingEvent.NORMALIZE_OK):
            ProcessingState.EXTRACTING_AUDIO,

        (ProcessingState.EXTRACTING_AUDIO, ProcessingEvent.AUDIO_OK):
            ProcessingState.GENERATING_THUMBNAIL,

        (ProcessingState.GENERATING_THUMBNAIL, ProcessingEvent.THUMBNAIL_OK):
            ProcessingState.DONE,
    }

    return transitions.get((state, event), ProcessingState.FAILED)