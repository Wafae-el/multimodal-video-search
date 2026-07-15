from random_events import run_random_sequence

from state_machine import ProcessingState


def test_random_sequences():

    for _ in range(100):

        state, artifacts = run_random_sequence()

        assert artifacts <= 1

        assert state in [
            ProcessingState.WAITING_UPLOAD,
            ProcessingState.PROCESSING,
            ProcessingState.COMPLETED,
            ProcessingState.FAILED,
        ]

def test_many_random_sequences():
    for _ in range(1000):
        state, artifacts = run_random_sequence()
        assert artifacts <= 1