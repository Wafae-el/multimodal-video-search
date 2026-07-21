from random_events import run_random_sequence

from packages.workflow.state_machine import ProcessingState


def test_random_sequences():
    for seed in range(100):
        state, artifacts = run_random_sequence(seed=seed)

        assert artifacts <= 1

        assert (
            (state == ProcessingState.DONE and artifacts == 1)
            or state == ProcessingState.FAILED
        )


def test_many_random_sequences():
    for seed in range(1000):
        state, artifacts = run_random_sequence(seed=seed)

        assert artifacts <= 1

        assert (
            (state == ProcessingState.DONE and artifacts == 1)
            or state == ProcessingState.FAILED
        )