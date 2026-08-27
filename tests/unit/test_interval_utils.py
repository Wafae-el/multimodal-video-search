import pytest

from packages.timeline.interval_utils import interval_iou


def test_identical_intervals():
    assert interval_iou((0, 10), (0, 10)) == 1.0


def test_partial_overlap():
    assert interval_iou((0, 10), (5, 15)) == 5 / 15


def test_no_overlap():
    assert interval_iou((0, 10), (20, 30)) == 0.0


def test_adjacent_intervals():
    assert interval_iou((0, 10), (10, 20)) == 0.0


def test_reverse_interval():
    with pytest.raises(ValueError):
        interval_iou((10, 0), (0, 10))


def test_duplicate_interval():
    assert interval_iou((5, 15), (5, 15)) == 1.0

from packages.timeline.interval_utils import merge_intervals


def test_merge_overlapping():
    assert merge_intervals([(0, 5), (3, 8)]) == [(0, 8)]


def test_merge_adjacent():
    assert merge_intervals([(0, 5), (5, 10)]) == [(0, 10)]


def test_merge_separated():
    assert merge_intervals([(0, 5), (10, 15)]) == [
        (0, 5),
        (10, 15),
    ]


def test_merge_unsorted():
    assert merge_intervals([(10, 15), (0, 5), (3, 8)]) == [
        (0, 8),
        (10, 15),
    ]


def test_merge_duplicates():
    assert merge_intervals([(0, 5), (0, 5)]) == [
        (0, 5),
    ]


def test_merge_empty():
    assert merge_intervals([]) == []

from packages.timeline.interval_utils import timeline_coverage


def test_coverage_empty():
    assert timeline_coverage([]) == 0


def test_coverage_single():
    assert timeline_coverage([(0, 10)]) == 10


def test_coverage_overlapping():
    assert timeline_coverage([(0, 5), (3, 8)]) == 8


def test_coverage_separated():
    assert timeline_coverage([(0, 5), (10, 15)]) == 10


def test_coverage_adjacent():
    assert timeline_coverage([(0, 5), (5, 10)]) == 10


def test_coverage_duplicates():
    assert timeline_coverage([(0, 5), (0, 5)]) == 5