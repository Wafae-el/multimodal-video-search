import pytest

from packages.workflow.state_machine import (
    ProcessingState,
    ProcessingEvent,
    next_state,
)


def test_upload_complete():
    assert (
        next_state(
            ProcessingState.UPLOADED,
            ProcessingEvent.UPLOAD_COMPLETE,
        )
        == ProcessingState.VALIDATING
    )


def test_validation_ok():
    assert (
        next_state(
            ProcessingState.VALIDATING,
            ProcessingEvent.VALIDATION_OK,
        )
        == ProcessingState.PROBING
    )


def test_probe_ok():
    assert (
        next_state(
            ProcessingState.PROBING,
            ProcessingEvent.PROBE_OK,
        )
        == ProcessingState.NORMALIZING
    )


def test_normalize_ok():
    assert (
        next_state(
            ProcessingState.NORMALIZING,
            ProcessingEvent.NORMALIZE_OK,
        )
        == ProcessingState.EXTRACTING_AUDIO
    )


def test_audio_ok():
    assert (
        next_state(
            ProcessingState.EXTRACTING_AUDIO,
            ProcessingEvent.AUDIO_OK,
        )
        == ProcessingState.GENERATING_THUMBNAIL
    )


def test_thumbnail_ok():
    assert (
        next_state(
            ProcessingState.GENERATING_THUMBNAIL,
            ProcessingEvent.THUMBNAIL_OK,
        )
        == ProcessingState.SEGMENTING
    )


def test_segment_ok():
    assert (
        next_state(
            ProcessingState.SEGMENTING,
            ProcessingEvent.SEGMENT_OK,
        )
        == ProcessingState.INDEXING_SPEECH
    )


def test_speech_index_ok():
    assert (
        next_state(
            ProcessingState.INDEXING_SPEECH,
            ProcessingEvent.SPEECH_INDEX_OK,
        )
        == ProcessingState.INDEXING_VISUAL
    )


def test_visual_index_ok():
    assert (
        next_state(
            ProcessingState.INDEXING_VISUAL,
            ProcessingEvent.VISUAL_INDEX_OK,
        )
        == ProcessingState.SCORING_AUDIO
    )


def test_audio_score_ok():
    assert (
        next_state(
            ProcessingState.SCORING_AUDIO,
            ProcessingEvent.AUDIO_SCORE_OK,
        )
        == ProcessingState.DONE
    )


def test_no_audio():
    assert (
        next_state(
            ProcessingState.VALIDATING,
            ProcessingEvent.NO_AUDIO,
        )
        == ProcessingState.NO_AUDIO
    )


def test_error():
    assert (
        next_state(
            ProcessingState.PROBING,
            ProcessingEvent.ERROR,
        )
        == ProcessingState.FAILED
    )


def test_invalid_transition():
    with pytest.raises(ValueError):
        next_state(
            ProcessingState.UPLOADED,
            ProcessingEvent.THUMBNAIL_OK,
        )
