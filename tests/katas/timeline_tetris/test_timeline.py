import pytest

from packages.segmentation.timeline import (
    Interval,
    interval_iou,
    merge_intervals,
    timeline_coverage,
)


def test_interval_iou_and_coverage():
    assert interval_iou(Interval(0, 1000), Interval(500, 1500)) == pytest.approx(1 / 3)
    assert timeline_coverage([Interval(0, 1000), Interval(500, 1500)], 3000) == pytest.approx(0.5)


def test_merge_preserves_gaps_and_rejects_reverse():
    assert merge_intervals([Interval(0, 1000), Interval(1200, 2000)], max_gap_ms=250) == [
        Interval(0, 2000)
    ]
    with pytest.raises(ValueError):
        Interval(100, 99)
