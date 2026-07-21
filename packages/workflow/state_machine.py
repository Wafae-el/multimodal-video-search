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
    # Événements de progression normale
    UPLOAD_COMPLETE = "UPLOAD_COMPLETE"
    VALIDATION_OK = "VALIDATION_OK"
    PROBE_OK = "PROBE_OK"
    NORMALIZE_OK = "NORMALIZE_OK"
    AUDIO_OK = "AUDIO_OK"
    THUMBNAIL_OK = "THUMBNAIL_OK"

    # Événements spéciaux / reprises
    RETRY = "RETRY"
    DUPLICATE_DELIVERY = "DUPLICATE_DELIVERY"
    OUTPUT_EXISTS = "OUTPUT_EXISTS"
    NO_AUDIO = "NO_AUDIO"

    # Événement d'erreur générique
    ERROR = "ERROR"


def next_state(state: ProcessingState, event: ProcessingEvent) -> ProcessingState:
    transitions = {
        # Parcours nominal
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

        # Gestion des erreurs spécifiques
        (ProcessingState.VALIDATING, ProcessingEvent.NO_AUDIO):
            ProcessingState.NO_AUDIO,

        (ProcessingState.PROBING, ProcessingEvent.ERROR):
            ProcessingState.FAILED,

        (ProcessingState.NORMALIZING, ProcessingEvent.ERROR):
            ProcessingState.FAILED,

        (ProcessingState.EXTRACTING_AUDIO, ProcessingEvent.ERROR):
            ProcessingState.FAILED,

        (ProcessingState.GENERATING_THUMBNAIL, ProcessingEvent.ERROR):
            ProcessingState.FAILED,
    }

    # Lève une exception explicite si la transition est invalide
    if (state, event) not in transitions:
        raise ValueError(f"Invalid transition: {state} + {event}")

    return transitions[(state, event)]