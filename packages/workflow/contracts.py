"""Typed workflow/activity contracts shared by the workflow and the activities.

Kept in a dedicated module so both ``workflows.py`` and ``activities.py`` can
import it without a circular dependency.
"""
from dataclasses import dataclass

# Shared retry configuration: used by the workflow's RetryPolicy (maximum
# attempts) and by activities to detect the final attempt so terminal FAILED is
# only written once retries are exhausted.
ACTIVITY_MAX_ATTEMPTS = 3


@dataclass
class ProcessAssetInput:
    """Only stable identifiers travel through Temporal history — never binary
    data, local paths, ffprobe JSON blobs or media arrays.

    ``asset_id`` carries a UUID value as a string so the payload stays
    JSON-serializable for Temporal's default data converter.
    """

    asset_id: str
    pipeline_version: str = "v1"


@dataclass
class WorkflowResult:
    asset_id: str
    status: str
    pipeline_version: str
