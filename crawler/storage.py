from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import pymysql
import redis

from crawler.config import Settings

T = TypeVar("T")


def make_redis_key(ip: str, port: int, protocol: str) -> str:
    return f"{ip}:{port}:{protocol}"


def _load_schema() -> str:
    """加载 schema.sql 文件内容"""
    schema_path = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
    return schema_path.read_text(encoding="utf-8")


def _init_database_and_schema(
    settings: Settings,
) -> None:
    """创建数据库和表，用于首次初始化或恢复"""
    try:
        # 先连接到 MySQL（不指定数据库）以创建库
        conn = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {settings.mysql_database} CHARACTER SET utf8mb4")
        finally:
            conn.close()

        # 再连接到目标数据库并执行 schema
        conn = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset="utf8mb4",
            autocommit=True,
        )
        try:
            schema = _load_schema()
            with conn.cursor() as cursor:
                for statement in schema.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        cursor.execute(stmt)
        finally:
            conn.close()
    except Exception:
        # 如果初始化失败，让上层处理
        raise


def _run_with_schema_retry(
    conn: pymysql.connections.Connection,
    settings: Optional[Settings],
    runner: Callable[[pymysql.cursors.Cursor], T],
) -> T:
    """
    执行数据库操作，如遇到表/库不存在错误则自动初始化并重试。
    
    Args:
        conn: MySQL 连接
        settings: 配置（用于初始化），为 None 时不尝试初始化
        runner: 执行实际操作的回调，接收 cursor 参数
    
    Returns:
        runner 的返回值
    """
    try:
        with conn.cursor() as cursor:
            return runner(cursor)
    except pymysql.err.ProgrammingError as e:
        # 1146: Table doesn't exist, 1049: Unknown database
        if e.args[0] in (1146, 1049) and settings:
            _init_database_and_schema(settings)
            # 重新建立连接并重试
            conn.ping(reconnect=True)
            with conn.cursor() as cursor:
                return runner(cursor)
        raise


def get_mysql_connection(settings: Settings) -> pymysql.connections.Connection:
    """获取 MySQL 连接，如果数据库/表不存在则自动初始化"""
    try:
        return pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset="utf8mb4",
            autocommit=True,
        )
    except pymysql.err.OperationalError as e:
        # 1049: Unknown database
        if e.args[0] == 1049:
            _init_database_and_schema(settings)
            return pymysql.connect(
                host=settings.mysql_host,
                port=settings.mysql_port,
                user=settings.mysql_user,
                password=settings.mysql_password,
                database=settings.mysql_database,
                charset="utf8mb4",
                autocommit=True,
            )
        raise


def get_redis_client(settings: Settings) -> redis.Redis:
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        decode_responses=True,
    )


_settings_for_retry: Optional[Settings] = None


def set_settings_for_retry(settings: Settings) -> None:
    """设置用于重试时的 Settings"""
    global _settings_for_retry
    _settings_for_retry = settings


def upsert_source(conn: pymysql.connections.Connection, name: str, url: str, parser_key: str) -> int:
    def runner(cursor):
        cursor.execute(
            """
            INSERT INTO proxy_sources (name, url, parser_key)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE url=VALUES(url), parser_key=VALUES(parser_key)
            """,
            (name, url, parser_key),
        )
        cursor.execute("SELECT id FROM proxy_sources WHERE name=%s", (name,))
        row = cursor.fetchone()
        return int(row[0])

    return _run_with_schema_retry(conn, _settings_for_retry, runner)


def upsert_proxy(
    conn: pymysql.connections.Connection,
    ip: str,
    port: int,
    protocol: str,
    anonymity: Optional[str],
    country: Optional[str],
    source_id: Optional[int],
) -> None:
    def runner(cursor):
        cursor.execute(
            """
            INSERT INTO proxy_ips (ip, port, protocol, anonymity, country, source_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              anonymity=VALUES(anonymity),
              country=VALUES(country),
              source_id=VALUES(source_id),
                            last_seen_at=CURRENT_TIMESTAMP,
                            is_deleted=0,
                            fail_window_start=NULL,
                            fail_count=0
            """,
            (ip, port, protocol, anonymity, country, source_id),
        )

    _run_with_schema_retry(conn, _settings_for_retry, runner)


def update_proxy_check(
    conn: pymysql.connections.Connection,
    ip: str,
    port: int,
    protocol: str,
    is_alive: bool,
    latency_ms: int,
    window_hours: int,
) -> None:
    alive_int = 1 if is_alive else 0

    def runner(cursor):
        cursor.execute(
            """
            UPDATE proxy_ips
            SET is_alive=%s,
                latency_ms=%s,
                last_checked_at=CURRENT_TIMESTAMP,
                fail_window_start=CASE
                    WHEN %s=1 THEN NULL
                    WHEN fail_window_start IS NULL THEN CURRENT_TIMESTAMP
                    WHEN TIMESTAMPDIFF(HOUR, fail_window_start, CURRENT_TIMESTAMP) >= %s THEN CURRENT_TIMESTAMP
                    ELSE fail_window_start
                END,
                fail_count=CASE
                    WHEN %s=1 THEN 0
                    WHEN fail_window_start IS NULL THEN 1
                    WHEN TIMESTAMPDIFF(HOUR, fail_window_start, CURRENT_TIMESTAMP) >= %s THEN 1
                    ELSE fail_count + 1
                END
            WHERE ip=%s AND port=%s AND protocol=%s
            """,
            (alive_int, latency_ms, alive_int, window_hours, alive_int, window_hours, ip, port, protocol),
        )

    _run_with_schema_retry(conn, _settings_for_retry, runner)


def fetch_check_batch(conn: pymysql.connections.Connection, batch_size: int) -> list[dict]:
    def runner(cursor):
        cursor.execute(
            """
            SELECT id, ip, port, protocol, fail_window_start, fail_count
            FROM proxy_ips
            WHERE is_deleted=0
            ORDER BY (last_checked_at IS NULL) DESC, last_checked_at ASC, id ASC
            LIMIT %s
            """,
            (batch_size,),
        )
        return list(cursor.fetchall())

    return _run_with_schema_retry(conn, _settings_for_retry, runner)


def update_proxy_check_with_window(
    conn: pymysql.connections.Connection,
    proxy_id: int,
    is_alive: bool,
    latency_ms: int,
    fail_window_start: Optional[datetime],
    fail_count: int,
    is_deleted: bool,
) -> None:
    def runner(cursor):
        cursor.execute(
            """
            UPDATE proxy_ips
            SET is_alive=%s,
                latency_ms=%s,
                last_checked_at=CURRENT_TIMESTAMP,
                fail_window_start=%s,
                fail_count=%s,
                is_deleted=%s
            WHERE id=%s
            """,
            (
                1 if is_alive else 0,
                latency_ms,
                fail_window_start,
                fail_count,
                1 if is_deleted else 0,
                proxy_id,
            ),
        )

    _run_with_schema_retry(conn, _settings_for_retry, runner)


def upsert_redis_pool(rds: redis.Redis, ip: str, port: int, protocol: str, score: int) -> None:
    key = make_redis_key(ip, port, protocol)
    try:
        rds.zadd("proxy:alive", {key: score})
    except Exception:
        return


def fetch_proxy_countries(conn: pymysql.connections.Connection, candidates: list[dict]) -> dict:
    def runner(cursor):
        if not candidates:
            return {}

        keys = [(candidate["ip"], candidate["port"], candidate["protocol"]) for candidate in candidates]
        placeholders = ",".join(["(%s,%s,%s)"] * len(keys))
        params = [value for key in keys for value in key]

        query = (
            "SELECT ip, port, protocol, country "
            "FROM proxy_ips "
            f"WHERE (ip, port, protocol) IN ({placeholders})"
        )

        mapping = {}
        cursor.execute(query, params)
        for row in cursor.fetchall():
            key = (row[1], row[2], row[3])
            mapping[key] = row[3]
        return mapping

    return _run_with_schema_retry(conn, _settings_for_retry, runner)


def fetch_mysql_candidates(
    conn: pymysql.connections.Connection,
    protocols: list[str],
    countries: Optional[list[str]],
    limit: int,
) -> list[dict]:
    def runner(cursor):
        if not protocols or limit <= 0:
            return []

        clauses = ["is_deleted=0", "is_alive=1"]
        params: list[object] = []

        protocol_placeholders = ",".join(["%s"] * len(protocols))
        clauses.append(f"protocol IN ({protocol_placeholders})")
        params.extend(protocols)

        if countries:
            country_placeholders = ",".join(["%s"] * len(countries))
            clauses.append(f"country IN ({country_placeholders})")
            params.extend(countries)

        where_clause = " AND ".join(clauses)
        query = (
            "SELECT ip, port, protocol, country, latency_ms "
            "FROM proxy_ips "
            f"WHERE {where_clause} "
            "ORDER BY (latency_ms IS NULL) ASC, latency_ms ASC, last_checked_at DESC "
            "LIMIT %s"
        )
        params.append(limit)

        cursor.execute(query, params)
        return list(cursor.fetchall())

    return _run_with_schema_retry(conn, _settings_for_retry, runner)


def insert_crawl_session(conn: pymysql.connections.Connection, session: dict[str, Any]) -> int:
    def runner(cursor):
        cursor.execute(
            """
            INSERT INTO crawl_session (
                user_url, page_count, ip_count, proxy_count,
                max_pages, max_pages_no_new_ip, page_fetch_timeout_seconds, cross_page_dedup,
                use_ai_fallback, status, error_message
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session.get("user_url", ""),
                int(session.get("page_count", 1)),
                int(session.get("ip_count", 0)),
                int(session.get("proxy_count", 0)),
                int(session.get("max_pages", 5)),
                int(session.get("max_pages_no_new_ip", 3)),
                int(session.get("page_fetch_timeout_seconds", 10)),
                1 if bool(session.get("cross_page_dedup", True)) else 0,
                1 if bool(session.get("use_ai_fallback", False)) else 0,
                session.get("status", "running"),
                session.get("error_message"),
            ),
        )
        return int(cursor.lastrowid)

    return _run_with_schema_retry(conn, _settings_for_retry, runner)


def insert_page_log(conn: pymysql.connections.Connection, log: dict[str, Any]) -> int:
    def runner(cursor):
        cursor.execute(
            """
            INSERT INTO crawl_page_log (
                session_id, page_url, page_number,
                html_size_bytes, table_count, list_count, json_block_count, text_block_count,
                detected_ips, detected_ip_port_pairs, extracted_proxies,
                http_status_code, fetch_time_seconds, parser_type,
                structure_confidence, extraction_confidence,
                parse_success, error_message,
                has_next_page, next_page_url, pagination_confidence
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(log.get("session_id", 0)),
                log.get("page_url", ""),
                int(log.get("page_number", 1)),
                int(log.get("html_size_bytes", 0)),
                int(log.get("table_count", 0)),
                int(log.get("list_count", 0)),
                int(log.get("json_block_count", 0)),
                int(log.get("text_block_count", 0)),
                int(log.get("detected_ips", 0)),
                int(log.get("detected_ip_port_pairs", 0)),
                int(log.get("extracted_proxies", 0)),
                log.get("http_status_code"),
                log.get("fetch_time_seconds"),
                log.get("parser_type"),
                float(log.get("structure_confidence", 0.0)),
                float(log.get("extraction_confidence", 0.0)),
                1 if bool(log.get("parse_success", True)) else 0,
                log.get("error_message"),
                1 if bool(log.get("has_next_page", False)) else 0,
                log.get("next_page_url"),
                float(log.get("pagination_confidence", 0.0)),
            ),
        )
        return int(cursor.lastrowid)

    return _run_with_schema_retry(conn, _settings_for_retry, runner)


def insert_review_queue_item(conn: pymysql.connections.Connection, data: dict[str, Any]) -> int:
    def runner(cursor):
        cursor.execute(
            """
            INSERT INTO proxy_review_queue (
                session_id, page_log_id, ip, port, protocol, detected_via,
                heuristic_confidence, validation_status,
                anomaly_detected, anomaly_reason,
                ai_improvement_needed, ai_improvement_reason, ai_improved_data,
                review_status, reviewer_notes,
                final_status, added_to_pool
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(data.get("session_id", 0)),
                int(data.get("page_log_id", 0)),
                data.get("ip", ""),
                int(data.get("port", 0)),
                data.get("protocol"),
                data.get("detected_via", "heuristic"),
                float(data.get("heuristic_confidence", 0.0)),
                data.get("validation_status", "pending"),
                1 if bool(data.get("anomaly_detected", False)) else 0,
                data.get("anomaly_reason"),
                1 if bool(data.get("ai_improvement_needed", False)) else 0,
                data.get("ai_improvement_reason"),
                data.get("ai_improved_data"),
                data.get("review_status", "pending"),
                data.get("reviewer_notes"),
                data.get("final_status"),
                1 if bool(data.get("added_to_pool", False)) else 0,
            ),
        )
        return int(cursor.lastrowid)

    return _run_with_schema_retry(conn, _settings_for_retry, runner)


def insert_llm_call_log(conn: pymysql.connections.Connection, log: dict[str, Any]) -> int:
    def runner(cursor):
        cursor.execute(
            """
            INSERT INTO llm_call_log (
                session_id, page_log_id,
                llm_provider, llm_model, llm_base_url,
                trigger_reason, input_context, input_tokens,
                response_text, output_tokens, total_tokens,
                extraction_results, extracted_proxy_count,
                cost_usd, call_status, error_message,
                retry_count, cache_hit, cache_key, call_time_seconds
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(log.get("session_id", 0)),
                log.get("page_log_id"),
                log.get("llm_provider", "openai-compatible"),
                log.get("llm_model", "unknown"),
                log.get("llm_base_url", ""),
                log.get("trigger_reason", "unknown"),
                log.get("input_context", "{}"),
                int(log.get("input_tokens", 0)),
                log.get("response_text"),
                int(log.get("output_tokens", 0)),
                int(log.get("total_tokens", 0)),
                log.get("extraction_results"),
                int(log.get("extracted_proxy_count", 0)),
                float(log.get("cost_usd", 0.0)),
                log.get("call_status", "pending"),
                log.get("error_message"),
                int(log.get("retry_count", 0)),
                1 if bool(log.get("cache_hit", False)) else 0,
                log.get("cache_key"),
                log.get("call_time_seconds"),
            ),
        )
        return int(cursor.lastrowid)

    return _run_with_schema_retry(conn, _settings_for_retry, runner)


def check_duplicate(
    conn: pymysql.connections.Connection,
    ip: str,
    port: int,
    protocol: str,
    session_id: Optional[int] = None,
) -> bool:
    def runner(cursor):
        if session_id is not None:
            cursor.execute(
                """
                SELECT COUNT(1)
                FROM proxy_review_queue
                WHERE session_id=%s AND ip=%s AND port=%s AND (protocol=%s OR protocol IS NULL)
                """,
                (session_id, ip, port, protocol),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(1)
                FROM proxy_ips
                WHERE ip=%s AND port=%s AND protocol=%s
                """,
                (ip, port, protocol),
            )

        row = cursor.fetchone()
        count = int(row[0]) if row else 0
        return count > 0

    return _run_with_schema_retry(conn, _settings_for_retry, runner)
