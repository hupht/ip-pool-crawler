from datetime import datetime, timedelta

from crawler.checker import apply_fail_window


def test_fail_window_sets_start_on_first_fail():
    now = datetime(2026, 2, 10, 0, 0, 0)
    result = apply_fail_window(
        now=now,
        fail_window_start=None,
        fail_count=0,
        success=False,
        window_hours=24,
        threshold=5,
    )
    assert result.fail_window_start == now
    assert result.fail_count == 1
    assert result.is_deleted is False


def test_fail_window_accumulates_within_window():
    now = datetime(2026, 2, 10, 1, 0, 0)
    start = now - timedelta(hours=2)
    result = apply_fail_window(
        now=now,
        fail_window_start=start,
        fail_count=2,
        success=False,
        window_hours=24,
        threshold=5,
    )
    assert result.fail_window_start == start
    assert result.fail_count == 3
    assert result.is_deleted is False


def test_fail_window_resets_outside_window():
    now = datetime(2026, 2, 10, 1, 0, 0)
    start = now - timedelta(hours=25)
    result = apply_fail_window(
        now=now,
        fail_window_start=start,
        fail_count=4,
        success=False,
        window_hours=24,
        threshold=5,
    )
    assert result.fail_window_start == now
    assert result.fail_count == 1
    assert result.is_deleted is False


def test_fail_window_resets_on_success():
    now = datetime(2026, 2, 10, 1, 0, 0)
    start = now - timedelta(hours=2)
    result = apply_fail_window(
        now=now,
        fail_window_start=start,
        fail_count=4,
        success=True,
        window_hours=24,
        threshold=5,
    )
    assert result.fail_window_start is None
    assert result.fail_count == 0
    assert result.is_deleted is False


def test_fail_window_deletes_on_threshold():
    now = datetime(2026, 2, 10, 1, 0, 0)
    start = now - timedelta(hours=1)
    result = apply_fail_window(
        now=now,
        fail_window_start=start,
        fail_count=4,
        success=False,
        window_hours=24,
        threshold=5,
    )
    assert result.fail_window_start == start
    assert result.fail_count == 5
    assert result.is_deleted is True
