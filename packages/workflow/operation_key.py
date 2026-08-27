"""Canonical, deterministic operation-key derivation."""

import hashlib
import json


def build_operation_key(
    asset_id: str,
    input_checksum: str,
    step: str,
    step_version: str,
    tool_version: str,
) -> str:
    data = {
        "asset_id": asset_id,
        "checksum": input_checksum,
        "step": step,
        "version": step_version,
        "tool_version": tool_version,
    }

    canonical = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode()
    ).hexdigest()