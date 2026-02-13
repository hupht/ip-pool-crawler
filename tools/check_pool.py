from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

from crawler.checker import apply_fail_window
from crawler.config import Settings
from crawler.storage import fetch_check_batch, get_mysql_connection, set_settings_for_retry, update_proxy_check_with_window
from crawler.runtime import load_settings
from crawler.validator import tcp_check


def _row_get(record: object, key: str, index: int):
    if isinstance(record, dict):
        return record.get(key)
    if isinstance(record, (list, tuple)):
        if 0 <= index < len(record):
            return record[index]
    return None


def check_proxy(ip: str, port: int, timeout: int, retries: int, retry_delay: int) -> tuple[bool, int]:
    # 失败时按固定间隔重试，返回可用性与延迟
    for attempt in range(retries):
        success, latency_ms = tcp_check(ip, port, timeout=timeout)
        if success:
            return True, latency_ms
        if attempt < retries - 1:
            time.sleep(retry_delay)
    return False, 0


def run_check_batch(settings: Settings) -> None:
    # 从数据库取批次并并发检测
    set_settings_for_retry(settings)
    
    mysql_conn = get_mysql_connection(settings)
    try:
        records = fetch_check_batch(mysql_conn, settings.check_batch_size)
        if not records:
            return

        # 线程池并发执行 TCP 探测
        with ThreadPoolExecutor(max_workers=settings.check_workers) as executor:
            future_map = {
                executor.submit(
                    check_proxy,
                    _row_get(record, "ip", 1),
                    int(_row_get(record, "port", 2)),
                    settings.http_timeout,
                    settings.check_retries,
                    settings.check_retry_delay,
                ): record
                for record in records
            }

            for future in as_completed(future_map):
                record = future_map[future]
                try:
                    success, latency_ms = future.result()
                except Exception:
                    success, latency_ms = False, 0

                now = datetime.now()
                fail_count = _row_get(record, "fail_count", 5) or 0
                # 基于失败窗口更新计数与软删除标记
                result = apply_fail_window(
                    now=now,
                    fail_window_start=_row_get(record, "fail_window_start", 4),
                    fail_count=fail_count,
                    success=success,
                    window_hours=settings.fail_window_hours,
                    threshold=settings.fail_threshold,
                )
                update_proxy_check_with_window(
                    mysql_conn,
                    int(_row_get(record, "id", 0)),
                    success,
                    latency_ms,
                    result.fail_window_start,
                    result.fail_count,
                    result.is_deleted,
                )
    finally:
        mysql_conn.close()


def main() -> None:
    settings = load_settings()
    run_check_batch(settings)


if __name__ == "__main__":
    main()
