from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass(frozen=True)
class FailWindowResult:
    fail_window_start: Optional[datetime]
    fail_count: int
    is_deleted: bool


def apply_fail_window(
    now: datetime,
    fail_window_start: Optional[datetime],
    fail_count: int,
    success: bool,
    window_hours: int,
    threshold: int,
) -> FailWindowResult:
    # 失败窗口统计：连续失败达到阈值则标记软删除
    if success:
        return FailWindowResult(fail_window_start=None, fail_count=0, is_deleted=False)

    window = timedelta(hours=window_hours)
    if fail_window_start is None or now - fail_window_start > window:
        new_start = now
        new_count = 1
    else:
        new_start = fail_window_start
        new_count = fail_count + 1

    is_deleted = new_count >= threshold and now - new_start <= window
    return FailWindowResult(fail_window_start=new_start, fail_count=new_count, is_deleted=is_deleted)
