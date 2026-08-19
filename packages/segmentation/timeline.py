from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Interval:
    start_ms: int
    end_ms: int
    label: str = ""

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms < 0:
            raise ValueError("interval timestamps must be non-negative")
        if self.end_ms < self.start_ms:
            raise ValueError("interval may not move backward in time")

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


def interval_iou(a: Interval, b: Interval) -> float:
    inter = max(0, min(a.end_ms, b.end_ms) - max(a.start_ms, b.start_ms))
    union = max(a.end_ms, b.end_ms) - min(a.start_ms, b.start_ms)
    return 0.0 if union == 0 else inter / union


def merge_intervals(intervals: list[Interval], max_gap_ms: int = 0) -> list[Interval]:
    if max_gap_ms < 0:
        raise ValueError("max_gap_ms must be non-negative")
    ordered = sorted(intervals, key=lambda item: (item.start_ms, item.end_ms, item.label))
    if not ordered:
        return []
    merged = [ordered[0]]
    for current in ordered[1:]:
        previous = merged[-1]
        if current.start_ms <= previous.end_ms + max_gap_ms:
            labels = "+".join(filter(None, [previous.label, current.label]))
            merged[-1] = Interval(previous.start_ms, max(previous.end_ms, current.end_ms), labels)
        else:
            merged.append(current)
    return merged


def timeline_coverage(intervals: list[Interval], video_duration_ms: int) -> float:
    if video_duration_ms <= 0:
        raise ValueError("video_duration_ms must be positive")
    covered = sum(item.duration_ms for item in merge_intervals(intervals))
    return min(1.0, covered / video_duration_ms)
