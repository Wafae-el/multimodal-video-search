import pytest

from packages.workflow.state_machine import (
    ProcessingState,
    ProcessingEvent,
    next_state,
)


def test_upload_complete():
    assert next_state(
        ProcessingState.UPLOADED,
        ProcessingEvent.UPLOAD_COMPLETE,
    ) == ProcessingState.VALIDATING


def test_validation_ok():
    assert next_state(
        ProcessingState.VALIDATING,
        ProcessingEvent.VALIDATION_OK,
    ) == ProcessingState.PROBING


def test_probe_ok():
    assert next_state(
        ProcessingState.PROBING,
        ProcessingEvent.PROBE_OK,
    ) == ProcessingState.NORMALIZING


def test_normalize_ok():
    assert next_state(
        ProcessingState.NORMALIZING,
        ProcessingEvent.NORMALIZE_OK,
    ) == ProcessingState.EXTRACTING_AUDIO


def test_audio_ok():
    assert next_state(
        ProcessingState.EXTRACTING_AUDIO,
        ProcessingEvent.AUDIO_OK,
    ) == ProcessingState.GENERATING_THUMBNAIL


def test_thumbnail_ok():
    assert next_state(
        ProcessingState.GENERATING_THUMBNAIL,
        ProcessingEvent.THUMBNAIL_OK,
    ) == ProcessingState.DETECTING_SCENES

def test_detect_scenes_ok():
    assert next_state(
        ProcessingState.DETECTING_SCENES,
        ProcessingEvent.SCENES_OK,
    ) == ProcessingState.DONE

def test_no_audio():
    assert next_state(
        ProcessingState.VALIDATING,
        ProcessingEvent.NO_AUDIO,
    ) == ProcessingState.NO_AUDIO


def test_error():
    assert next_state(
        ProcessingState.PROBING,
        ProcessingEvent.ERROR,
    ) == ProcessingState.FAILED


def test_invalid_transition():
    with pytest.raises(ValueError):
        next_state(
            ProcessingState.UPLOADED,
            ProcessingEvent.THUMBNAIL_OK,
        )
