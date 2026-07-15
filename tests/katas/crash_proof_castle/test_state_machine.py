from state_machine import ProcessingState, ProcessingEvent


def test_processing_states():

    assert ProcessingState.WAITING_UPLOAD.value == "WAITING_UPLOAD"
    assert ProcessingState.PROCESSING.value == "PROCESSING"
    assert ProcessingState.COMPLETED.value == "COMPLETED"
    assert ProcessingState.FAILED.value == "FAILED"


def test_processing_events():

    assert ProcessingEvent.UPLOAD_COMPLETE.value == "upload_complete"
    assert ProcessingEvent.WORKER_CRASH.value == "worker_crash"
    assert ProcessingEvent.RETRY.value == "retry"
    assert ProcessingEvent.DUPLICATE_DELIVERY.value == "duplicate_delivery"
    assert ProcessingEvent.OUTPUT_EXISTS.value == "output_exists"

from state_machine import next_state

def test_upload_complete():

    assert next_state(
        ProcessingState.WAITING_UPLOAD,
        ProcessingEvent.UPLOAD_COMPLETE,
    ) == ProcessingState.PROCESSING


def test_worker_crash():

    assert next_state(
        ProcessingState.PROCESSING,
        ProcessingEvent.WORKER_CRASH,
    ) == ProcessingState.FAILED


def test_retry():

    assert next_state(
        ProcessingState.FAILED,
        ProcessingEvent.RETRY,
    ) == ProcessingState.PROCESSING


def test_output_exists():

    assert next_state(
        ProcessingState.PROCESSING,
        ProcessingEvent.OUTPUT_EXISTS,
    ) == ProcessingState.COMPLETED


def test_duplicate_delivery():

    assert next_state(
        ProcessingState.COMPLETED,
        ProcessingEvent.DUPLICATE_DELIVERY,
    ) == ProcessingState.COMPLETED