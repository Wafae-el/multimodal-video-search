from enum import Enum


class ProcessingState(str, Enum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    PROBING = "PROBING"
    NORMALIZING = "NORMALIZING"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    GENERATING_THUMBNAIL = "GENERATING_THUMBNAIL"
    SEGMENTING = "SEGMENTING"
    INDEXING_SPEECH = "INDEXING_SPEECH"
    INDEXING_VISUAL = "INDEXING_VISUAL"
    SCORING_AUDIO = "SCORING_AUDIO"
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
    SEGMENT_OK = "SEGMENT_OK"
    SPEECH_INDEX_OK = "SPEECH_INDEX_OK"
    VISUAL_INDEX_OK = "VISUAL_INDEX_OK"
    AUDIO_SCORE_OK = "AUDIO_SCORE_OK"

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
        (ProcessingState.UPLOADED, ProcessingEvent.UPLOAD_COMPLETE): ProcessingState.VALIDATING,
        (ProcessingState.VALIDATING, ProcessingEvent.VALIDATION_OK): ProcessingState.PROBING,
        (ProcessingState.PROBING, ProcessingEvent.PROBE_OK): ProcessingState.NORMALIZING,
        (
            ProcessingState.NORMALIZING,
            ProcessingEvent.NORMALIZE_OK,
        ): ProcessingState.EXTRACTING_AUDIO,
        (
            ProcessingState.EXTRACTING_AUDIO,
            ProcessingEvent.AUDIO_OK,
        ): ProcessingState.GENERATING_THUMBNAIL,
        (
            ProcessingState.GENERATING_THUMBNAIL,
            ProcessingEvent.THUMBNAIL_OK,
        ): ProcessingState.SEGMENTING,
        (ProcessingState.SEGMENTING, ProcessingEvent.SEGMENT_OK): ProcessingState.INDEXING_SPEECH,
        (
            ProcessingState.INDEXING_SPEECH,
            ProcessingEvent.SPEECH_INDEX_OK,
        ): ProcessingState.INDEXING_VISUAL,
        (
            ProcessingState.INDEXING_VISUAL,
            ProcessingEvent.VISUAL_INDEX_OK,
        ): ProcessingState.SCORING_AUDIO,
        (ProcessingState.SCORING_AUDIO, ProcessingEvent.AUDIO_SCORE_OK): ProcessingState.DONE,
        # Gestion des erreurs spécifiques
        (ProcessingState.VALIDATING, ProcessingEvent.NO_AUDIO): ProcessingState.NO_AUDIO,
        (ProcessingState.PROBING, ProcessingEvent.ERROR): ProcessingState.FAILED,
        (ProcessingState.NORMALIZING, ProcessingEvent.ERROR): ProcessingState.FAILED,
        (ProcessingState.EXTRACTING_AUDIO, ProcessingEvent.ERROR): ProcessingState.FAILED,
        (ProcessingState.GENERATING_THUMBNAIL, ProcessingEvent.ERROR): ProcessingState.FAILED,
        (ProcessingState.SEGMENTING, ProcessingEvent.ERROR): ProcessingState.FAILED,
        (ProcessingState.INDEXING_SPEECH, ProcessingEvent.ERROR): ProcessingState.FAILED,
        (ProcessingState.INDEXING_VISUAL, ProcessingEvent.ERROR): ProcessingState.FAILED,
        (ProcessingState.SCORING_AUDIO, ProcessingEvent.ERROR): ProcessingState.FAILED,
    }

    # Lève une exception explicite si la transition est invalide
    if (state, event) not in transitions:
        raise ValueError(f"Invalid transition: {state} + {event}")

    return transitions[(state, event)]


# ---------------------------------------------------------------------------
# Idempotent, monotonic advancement (used for Temporal-retry safety).
#
# ``next_state`` above is strict and rejects any transition that is not the
# exact expected one — which is correct for validating a single event, but a
# retried activity may find the asset already advanced (VALIDATING, PROBING,
# FAILED, ...). To stay retry-safe we advance along a linear ordering and treat
# "already at or past the target" as a no-op instead of an error.
# ---------------------------------------------------------------------------

STATE_ORDER = [
    ProcessingState.UPLOADED,
    ProcessingState.VALIDATING,
    ProcessingState.PROBING,
    ProcessingState.NORMALIZING,
    ProcessingState.EXTRACTING_AUDIO,
    ProcessingState.GENERATING_THUMBNAIL,
    ProcessingState.SEGMENTING,
    ProcessingState.INDEXING_SPEECH,
    ProcessingState.INDEXING_VISUAL,
    ProcessingState.SCORING_AUDIO,
    ProcessingState.DONE,
]
STATE_RANK = {state: index for index, state in enumerate(STATE_ORDER)}

TERMINAL_STATES = {
    ProcessingState.DONE,
    ProcessingState.FAILED,
    ProcessingState.NO_AUDIO,
}


def is_at_or_past(current: ProcessingState, target: ProcessingState) -> bool:
    """True if ``current`` is the same as, or further along than, ``target``."""
    if current not in STATE_RANK or target not in STATE_RANK:
        return False
    return STATE_RANK[current] >= STATE_RANK[target]
