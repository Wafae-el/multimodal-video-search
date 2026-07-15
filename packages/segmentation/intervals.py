from typing import Tuple, List


def interval_iou(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """
    Compute the Intersection over Union (IoU)
    between two time intervals.
    """

    start = max(a[0], b[0])
    end = min(a[1], b[1])

    intersection = max(0, end - start)

    union = max(a[1], b[1]) - min(a[0], b[0])

    if union == 0:
        return 0.0

    return intersection / union


def merge_intervals(
    intervals: List[Tuple[int, int]],
    max_gap: int,
) -> List[Tuple[int, int]]:

    if not intervals:
        return []

    intervals = sorted(intervals)

    merged = [intervals[0]]

    for current_start, current_end in intervals[1:]:

        last_start, last_end = merged[-1]

        if current_start <= last_end + max_gap:

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


def timeline_coverage(
    intervals: List[Tuple[int, int]],
    duration: int,
) -> float:

    if duration <= 0:
        return 0.0

    merged = merge_intervals(intervals, max_gap=0)

    covered = sum(
        end - start
        for start, end in merged
    )

    return covered / duration