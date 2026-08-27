from packages.workflow.operation_key import build_operation_key


def test_operation_key_is_deterministic():
    key1 = build_operation_key(
        "asset-1",
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    )

    key2 = build_operation_key(
        "asset-1",
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    )

    assert key1 == key2


def test_operation_key_changes_when_asset_changes():
    assert build_operation_key(
        "asset-1",
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    ) != build_operation_key(
        "asset-2",
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    )


def test_operation_key_changes_when_step_changes():
    assert build_operation_key(
        "asset-1",
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    ) != build_operation_key(
        "asset-1",
        "abc123",
        "thumbnail",
        "v1",
        "whisper-large-v3",
    )


def test_operation_key_changes_when_step_version_changes():
    assert build_operation_key(
        "asset-1",
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    ) != build_operation_key(
        "asset-1",
        "abc123",
        "ffmpeg",
        "v2",
        "whisper-large-v3",
    )


def test_operation_key_changes_when_model_version_changes():
    assert build_operation_key(
        "asset-1",
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v3",
    ) != build_operation_key(
        "asset-1",
        "abc123",
        "ffmpeg",
        "v1",
        "whisper-large-v4",
    )


def test_operation_key_avoids_ambiguous_concatenation():
    key1 = build_operation_key(
        "asset-1",
        "ab",
        "c",
        "d",
        "e",
    )

    key2 = build_operation_key(
        "asset-1",
        "a",
        "bc",
        "d",
        "e",
    )
    assert key1 != key2