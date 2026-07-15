import hashlib


def operation_key(
    asset_checksum: str,
    step: str,
    step_version: str,
    model_version: str,
) -> str:
    """
    Compute a deterministic operation key.
    """

    data = (
        asset_checksum
        + step
        + step_version
        + model_version
    )

    return hashlib.sha256(
        data.encode("utf-8")
    ).hexdigest()