from typing import Tuple


Interval = Tuple[float, float]


def interval_iou(a: Interval, b: Interval) -> float:
    """
    Compute the Temporal Intersection over Union (tIoU)
    between two intervals.

    Args:
        a: (start, end)
        b: (start, end)

    Returns:
        float between 0 and 1.

    Raises:
        ValueError:
            if an interval is invalid.
    """

    a_start, a_end = a
    b_start, b_end = b

    if a_start > a_end:
        raise ValueError("Invalid interval: start must be <= end.")

    if b_start > b_end:
        raise ValueError("Invalid interval: start must be <= end.")

    intersection = max(
        0,
        min(a_end, b_end) - max(a_start, b_start),
    )

    union = max(a_end, b_end) - min(a_start, b_start)

    if union == 0:
        return 1.0

    return intersection / union

def merge_intervals(intervals: list[Interval]) -> list[Interval]:
    """
    Merge overlapping or adjacent intervals.
    """

    if not intervals:
        return []

    for start, end in intervals:
        if start > end:
            raise ValueError("Invalid interval.")

    intervals = sorted(intervals)

    merged = [intervals[0]]

    for current_start, current_end in intervals[1:]:
        last_start, last_end = merged[-1]

        if current_start <= last_end:
            merged[-1] = (
                last_start,
                max(last_end, current_end),
            )
        else:
            merged.append(
                (
                    current_start,
                    current_end,
                )
            )

    return merged

def timeline_coverage(intervals: list[Interval]) -> float:
    """
    Return the total covered duration after merging
    overlapping and adjacent intervals.
    """

    merged = merge_intervals(intervals)

    return sum(
        end - start
        for start, end in merged
    )