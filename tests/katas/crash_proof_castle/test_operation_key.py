from operation_key import operation_key


def test_operation_key_is_deterministic():

    key1 = operation_key(
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    )

    key2 = operation_key(
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    )

    assert key1 == key2


def test_operation_key_changes_when_input_changes():

    key1 = operation_key(
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    )

    key2 = operation_key(
        "xyz789",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    )

    assert key1 != key2
    