"""Canonical, deterministic operation-key derivation.

The key is a SHA-256 over a canonical JSON object (sorted keys, no whitespace)
of the identifying fields, so it is unambiguous — unlike direct string
concatenation, ``("ab","c")`` and ``("a","bc")`` produce different keys.
"""
import hashlib
import json


def build_operation_key(
    input_checksum: str,
    step: str,
    step_version: str,
    tool_version: str,
) -> str:
    data = {
        "checksum": input_checksum,
        "step": step,
        "version": step_version,
        "tool_version": tool_version,
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
