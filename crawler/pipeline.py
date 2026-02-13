from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Tuple

from crawler.config import Settings
from crawler.fetcher import fetch_source
from crawler.http_validator import HTTPValidator
from crawler.parsers import (
    parse_geonode,
    parse_proxy_list_download_http,
    parse_proxy_list_download_https,
    parse_proxy_list_download_socks4,
    parse_proxy_list_download_socks5,
)
from crawler.sources import Source, get_sources
from crawler.storage import (
    get_mysql_connection,
    get_redis_client,
    set_settings_for_retry,
    update_proxy_check,
    upsert_proxy,
    upsert_redis_pool,
    upsert_source,
)
from crawler.validator import score_proxy, tcp_check


# 来源解析器映射，确保 source.parser_key 可定位到具体解析函数
PARSER_MAP = {
    "proxy_list_download_http": parse_proxy_list_download_http,
    "proxy_list_download_https": parse_proxy_list_download_https,
    "proxy_list_download_socks4": parse_proxy_list_download_socks4,
    "proxy_list_download_socks5": parse_proxy_list_download_socks5,
    "geonode": parse_geonode,
}


def normalize_record(record: Dict[str, object]) -> Dict[str, object]:
    # 将不同来源记录规范化为统一字段
    ip = str(record.get("ip", "")).strip()
    port = int(record.get("port"))
    protocol = str(record.get("protocol", "http")).lower()
    anonymity = record.get("anonymity")
    country = record.get("country")
    return {
        "ip": ip,
        "port": port,
        "protocol": protocol,
        "anonymity": anonymity,
        "country": country,
    }


def parse_by_source(source: Source, raw: str) -> List[Dict[str, object]]:
    # 根据来源选择解析器
    parser = PARSER_MAP.get(source.parser_key)
    if not parser:
        return []
    return parser(raw)


def _fetch_and_parse(source: Source, settings: Settings) -> List[Dict[str, object]]:
    # 拉取并解析，失败返回空列表
    raw, _status = fetch_source(source, settings)
    if not raw:
        return []
    return parse_by_source(source, raw)


def _check_record(record: Dict[str, object], timeout: int) -> Tuple[bool, int]:
    # HTTP 方式探测单条代理（失败时回退 TCP）
    try:
        protocol = str(record.get("protocol", "http"))
        result = HTTPValidator.validate_with_http(
            ip=record["ip"],
            port=record["port"],
            protocol=protocol,
            timeout=timeout,
        )
        if result.protocol_verified:
            return result.is_reachable, result.response_time_ms
        return tcp_check(record["ip"], record["port"], timeout=timeout)
    except Exception:
        return False, 0


def run_once(settings: Settings, quick_test: bool = False, quick_record_limit: int = 1) -> None:
    # 单次抓取流程：抓取 -> 解析 -> 入库 -> 验证 -> 更新 Redis
    set_settings_for_retry(settings)
    
    sources = get_sources()
    mysql_conn = get_mysql_connection(settings)
    redis_client = get_redis_client(settings)

    quick_limit = max(1, int(quick_record_limit))

    try:
        source_rows = []
        for source in sources:
            source_id = upsert_source(mysql_conn, source.name, source.url, source.parser_key)
            source_rows.append((source, source_id))

        if quick_test:
            for source, source_id in source_rows:
                try:
                    records = _fetch_and_parse(source, settings)
                except Exception:
                    records = []

                normalized_records = []
                for record in _normalize_records(records):
                    normalized_records.append(record)
                    if len(normalized_records) >= quick_limit:
                        break

                if not normalized_records:
                    continue

                for record in normalized_records:
                    upsert_proxy(
                        mysql_conn,
                        record["ip"],
                        record["port"],
                        record["protocol"],
                        record.get("anonymity"),
                        record.get("country"),
                        source_id,
                    )
                    success, latency_ms = _check_record(record, settings.http_timeout)
                    score = score_proxy(latency_ms=latency_ms, success=success)
                    update_proxy_check(
                        mysql_conn,
                        record["ip"],
                        record["port"],
                        record["protocol"],
                        success,
                        latency_ms,
                        settings.fail_window_hours,
                    )
                    if success:
                        upsert_redis_pool(
                            redis_client,
                            record["ip"],
                            record["port"],
                            record["protocol"],
                            score,
                        )
                break
            return

        validate_futures = {}
        # 抓取与验证并发执行，提升吞吐
        with ThreadPoolExecutor(max_workers=settings.source_workers) as fetch_pool, ThreadPoolExecutor(
            max_workers=settings.validate_workers
        ) as validate_pool:
            future_map = {
                fetch_pool.submit(_fetch_and_parse, source, settings): (source, source_id)
                for source, source_id in source_rows
            }
            for future in as_completed(future_map):
                source, source_id = future_map[future]
                try:
                    records = future.result()
                except Exception:
                    records = []

                # 入库后提交 TCP 校验任务
                for record in _normalize_records(records):
                    upsert_proxy(
                        mysql_conn,
                        record["ip"],
                        record["port"],
                        record["protocol"],
                        record.get("anonymity"),
                        record.get("country"),
                        source_id,
                    )
                    validate_futures[
                        validate_pool.submit(_check_record, record, settings.http_timeout)
                    ] = record

            # 收集验证结果并更新存储与 Redis
            for future in as_completed(validate_futures):
                record = validate_futures[future]
                try:
                    success, latency_ms = future.result()
                except Exception:
                    success, latency_ms = False, 0
                score = score_proxy(latency_ms=latency_ms, success=success)
                update_proxy_check(
                    mysql_conn,
                    record["ip"],
                    record["port"],
                    record["protocol"],
                    success,
                    latency_ms,
                    settings.fail_window_hours,
                )
                if success:
                    upsert_redis_pool(redis_client, record["ip"], record["port"], record["protocol"], score)
    finally:
        mysql_conn.close()


def _normalize_records(records: Iterable[Dict[str, object]]) -> Iterable[Dict[str, object]]:
    for record in records:
        normalized = normalize_record(record)
        if normalized["ip"] and normalized["port"]:
            yield normalized
