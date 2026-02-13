from dataclasses import dataclass
import time
from typing import Dict, List, Optional, Set, Tuple

import requests

from crawler.config import Settings
from crawler.error_handler import ErrorHandler
from crawler.js_fetcher import fetch_page_with_playwright
from crawler.logging import get_logger
from crawler.pagination_controller import PaginationController
from crawler.pagination_detector import PaginationDetector
from crawler.proxy_validator import ProxyValidator
from crawler.storage import (
    check_duplicate,
    get_mysql_connection,
    insert_crawl_session,
    insert_llm_call_log,
    insert_page_log,
    insert_review_queue_item,
    set_settings_for_retry,
    upsert_proxy,
    upsert_source,
)
from crawler.universal_parser import UniversalParser


@dataclass
class DynamicCrawlResult:
    url: str
    pages_crawled: int
    extracted: int
    valid: int
    invalid: int
    stored: int
    session_id: Optional[int] = None


class DynamicCrawler:
    def __init__(self, settings: Settings):
        self.settings = settings
        try:
            self.audit_logger = get_logger(settings)
        except Exception:
            self.audit_logger = None

    def _fetch_page(self, url: str, render_js: bool = False) -> str:
        headers = {"User-Agent": self.settings.user_agent}
        timeout = max(1, int(self.settings.page_fetch_timeout_seconds))
        started = time.time()
        response = None
        try:
            if render_js:
                text = fetch_page_with_playwright(
                    url=url,
                    user_agent=self.settings.user_agent,
                    timeout_seconds=timeout,
                )
                status_code = 200
            else:
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                text = response.text
                status_code = int(response.status_code)
            if self.audit_logger is not None:
                self.audit_logger.log_http_request(
                    url=url,
                    status_code=status_code,
                    bytes_received=len((text or "").encode("utf-8", errors="ignore")),
                    latency_ms=int((time.time() - started) * 1000),
                    level="INFO",
                )
            return text
        except Exception as exc:
            if self.audit_logger is not None:
                self.audit_logger.log_http_request(
                    url=url,
                    status_code=int(getattr(response, "status_code", 0) or 0),
                    bytes_received=0,
                    latency_ms=int((time.time() - started) * 1000),
                    error=exc,
                    level="ERROR",
                )
            raise

    @staticmethod
    def _to_proxy_dicts(extracted_items: List[object]) -> List[Dict[str, object]]:
        proxy_dicts = []
        for item in extracted_items:
            if item.port is None:
                continue
            proxy_dicts.append(
                {
                    "ip": item.ip,
                    "port": item.port,
                    "protocol": item.protocol or "http",
                }
            )
        return proxy_dicts

    @staticmethod
    def _dedup_valid_proxies(valid_proxies: List[Dict[str, object]]) -> List[Dict[str, object]]:
        seen: Set[Tuple[str, int, str]] = set()
        unique_items: List[Dict[str, object]] = []
        for proxy in valid_proxies:
            key = (str(proxy["ip"]), int(proxy["port"]), str(proxy.get("protocol") or "http"))
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(proxy)
        return unique_items

    def crawl(
        self,
        url: str,
        max_pages: int = 1,
        use_ai: bool = False,
        no_store: bool = False,
        verbose: bool = False,
        render_js: bool = False,
    ) -> DynamicCrawlResult:
        effective_use_ai = bool(use_ai or self.settings.use_ai_fallback)
        error_handler = ErrorHandler() if effective_use_ai else None

        limit = max(1, int(max_pages))
        current_url = url
        controller = PaginationController(
            max_pages=limit,
            max_pages_no_new_ip=max(1, int(self.settings.max_pages_no_new_ip)),
        )

        all_extracted: List[Dict[str, object]] = []
        all_valid_seen: Set[Tuple[str, int, str]] = set()
        pages_crawled = 0

        session_id: Optional[int] = None
        source_id: Optional[int] = None
        conn = None
        started = time.time()
        last_page_number = 1
        last_page_url = url

        if verbose:
            print(
                f"crawl-custom start url={url} max_pages={limit} "
                f"use_ai={effective_use_ai} no_store={no_store} render_js={render_js}"
            )

        if self.audit_logger is not None:
            self.audit_logger.log_pipeline_event(
                event_type="START",
                module="crawl-custom",
                data_count=None,
                duration_ms=0,
                level="INFO",
            )

        if not no_store:
            set_settings_for_retry(self.settings)
            conn = get_mysql_connection(self.settings)
            session_id = insert_crawl_session(
                conn,
                {
                    "user_url": url,
                    "page_count": 0,
                    "ip_count": 0,
                    "proxy_count": 0,
                    "max_pages": limit,
                    "max_pages_no_new_ip": self.settings.max_pages_no_new_ip,
                    "page_fetch_timeout_seconds": self.settings.page_fetch_timeout_seconds,
                    "cross_page_dedup": self.settings.cross_page_dedup,
                    "use_ai_fallback": self.settings.use_ai_fallback,
                    "status": "running",
                },
            )
            source_id = upsert_source(conn, "custom-url", url, "universal_parser")

        try:
            while current_url and controller.should_continue():
                if not controller.mark_visited(current_url):
                    break

                page_number = pages_crawled + 1
                last_page_number = page_number
                last_page_url = current_url
                if verbose:
                    print(f"crawl-custom fetching page={page_number} url={current_url}")
                html = self._fetch_page(current_url, render_js=render_js)
                page_reviews: List[Dict[str, object]] = []
                ai_meta: Dict[str, object] = {"ai_called": False, "ai_result": None, "ai_reason": None}

                if error_handler is not None:
                    valid_data, review_data, meta = error_handler.process_page_with_meta(
                        html,
                        context={"url": current_url, "page_number": page_number},
                    )
                    page_proxy_dicts = [
                        {
                            "ip": item.get("ip"),
                            "port": item.get("port"),
                            "protocol": item.get("protocol") or "http",
                        }
                        for item in valid_data
                        if item.get("ip") and item.get("port") is not None
                    ]
                    page_reviews = review_data
                    ai_meta = meta
                else:
                    extracted, _stats = UniversalParser.extract_all(html)
                    deduped = UniversalParser.deduplicate_proxies(extracted)
                    page_proxy_dicts = self._to_proxy_dicts(deduped)
                all_extracted.extend(page_proxy_dicts)

                page_valid_proxies, _page_stats = ProxyValidator.batch_validate(page_proxy_dicts)
                new_count = 0
                for proxy in page_valid_proxies:
                    key = (str(proxy["ip"]), int(proxy["port"]), str(proxy.get("protocol") or "http"))
                    if key not in all_valid_seen:
                        all_valid_seen.add(key)
                        new_count += 1

                controller.record_page_ips(new_count)
                pages_crawled += 1

                pagination = PaginationDetector.detect_pagination(html, current_url)
                next_url = controller.get_next_url(current_url, pagination.next_page_url)

                if verbose:
                    print(
                        f"crawl-custom page={page_number} extracted={len(page_proxy_dicts)} "
                        f"valid={len(page_valid_proxies)} new={new_count} has_next={bool(next_url)}"
                    )

                page_log_id: Optional[int] = None
                if conn is not None and session_id is not None:
                    page_log_id = insert_page_log(
                        conn,
                        {
                            "session_id": session_id,
                            "page_url": current_url,
                            "page_number": page_number,
                            "html_size_bytes": len(html.encode("utf-8", errors="ignore")),
                            "detected_ips": len({item.get("ip") for item in page_proxy_dicts}),
                            "detected_ip_port_pairs": len(page_proxy_dicts),
                            "extracted_proxies": len(page_proxy_dicts),
                            "parse_success": True,
                            "has_next_page": bool(next_url),
                            "next_page_url": next_url,
                            "pagination_confidence": pagination.confidence,
                            "extraction_confidence": 1.0 if page_proxy_dicts else 0.0,
                        },
                    )

                    if page_log_id is not None:
                        for review in page_reviews:
                            review_ip = str(review.get("ip") or "")
                            review_port = int(review.get("port") or 0)
                            review_protocol = str(review.get("protocol") or "http")
                            if not review_ip or review_port <= 0:
                                continue
                            if check_duplicate(conn, review_ip, review_port, review_protocol, session_id=session_id):
                                continue
                            insert_review_queue_item(
                                conn,
                                {
                                    "session_id": session_id,
                                    "page_log_id": page_log_id,
                                    "ip": review_ip,
                                    "port": review_port,
                                    "protocol": review_protocol,
                                    "detected_via": review.get("source", "heuristic"),
                                    "heuristic_confidence": float(review.get("confidence", 0.0)),
                                    "validation_status": "pending",
                                    "anomaly_detected": bool(review.get("review_reason")),
                                    "anomaly_reason": review.get("review_reason"),
                                },
                            )

                        ai_result = ai_meta.get("ai_result") if isinstance(ai_meta, dict) else None
                        if ai_meta.get("ai_called") and isinstance(ai_result, dict):
                            tokens = ai_result.get("tokens") if isinstance(ai_result.get("tokens"), dict) else {}
                            insert_llm_call_log(
                                conn,
                                {
                                    "session_id": session_id,
                                    "page_log_id": page_log_id,
                                    "llm_provider": "openai-compatible",
                                    "llm_model": error_handler.llm_config.model if error_handler else "unknown",
                                    "llm_base_url": error_handler.llm_config.base_url if error_handler else "",
                                    "trigger_reason": ai_meta.get("ai_reason") or "unknown",
                                    "input_context": str({"url": current_url, "page_number": page_number}),
                                    "input_tokens": int(tokens.get("input", 0)),
                                    "response_text": None,
                                    "output_tokens": int(tokens.get("output", 0)),
                                    "total_tokens": int(tokens.get("total", 0)),
                                    "extraction_results": str(ai_result.get("proxies", [])),
                                    "extracted_proxy_count": len(ai_result.get("proxies", [])),
                                    "cost_usd": float(ai_result.get("cost_usd", 0.0)),
                                    "call_status": "success" if "error" not in ai_result else "failed",
                                    "error_message": ai_result.get("error"),
                                    "cache_hit": bool(ai_result.get("cache_hit", False)),
                                },
                            )

                current_url = next_url

            valid_proxies, validate_stats = ProxyValidator.batch_validate(all_extracted)
            valid_proxies = self._dedup_valid_proxies(valid_proxies)

            stored = 0
            if conn is not None and source_id is not None and valid_proxies:
                for proxy in valid_proxies:
                    if session_id is not None and check_duplicate(
                        conn,
                        str(proxy["ip"]),
                        int(proxy["port"]),
                        str(proxy.get("protocol") or "http"),
                        session_id=session_id,
                    ):
                        continue
                    upsert_proxy(
                        conn,
                        str(proxy["ip"]),
                        int(proxy["port"]),
                        str(proxy.get("protocol") or "http"),
                        None,
                        None,
                        source_id,
                    )
                    stored += 1

            if conn is not None and session_id is not None:
                duration_seconds = int(max(0, time.time() - started))
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE crawl_session
                        SET page_count=%s,
                            ip_count=%s,
                            proxy_count=%s,
                            status='completed',
                            completed_at=CURRENT_TIMESTAMP,
                            duration_seconds=%s,
                            error_message=NULL
                        WHERE id=%s
                        """,
                        (pages_crawled, len(all_extracted), stored, duration_seconds, session_id),
                    )

            if verbose:
                print(
                    f"crawl-custom url={url} pages={pages_crawled} "
                    f"extracted={len(all_extracted)} valid={len(valid_proxies)} stored={stored}"
                )

            if self.audit_logger is not None:
                self.audit_logger.log_pipeline_event(
                    event_type="COMPLETE",
                    module="crawl-custom",
                    data_count=len(all_extracted),
                    duration_ms=int(max(0, (time.time() - started) * 1000)),
                    level="INFO",
                )

            return DynamicCrawlResult(
                url=url,
                pages_crawled=pages_crawled,
                extracted=len(all_extracted),
                valid=len(valid_proxies),
                invalid=validate_stats["invalid"],
                stored=stored,
                session_id=session_id,
            )
        except Exception as exc:
            if conn is not None and session_id is not None:
                try:
                    insert_page_log(
                        conn,
                        {
                            "session_id": session_id,
                            "page_url": last_page_url,
                            "page_number": int(last_page_number),
                            "html_size_bytes": 0,
                            "detected_ips": 0,
                            "detected_ip_port_pairs": 0,
                            "extracted_proxies": 0,
                            "parse_success": False,
                            "error_message": str(exc),
                            "has_next_page": False,
                            "next_page_url": None,
                            "pagination_confidence": 0.0,
                            "extraction_confidence": 0.0,
                        },
                    )
                except Exception:
                    pass

            if conn is not None and session_id is not None:
                duration_seconds = int(max(0, time.time() - started))
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE crawl_session
                        SET status='failed',
                            completed_at=CURRENT_TIMESTAMP,
                            duration_seconds=%s,
                            error_message=%s
                        WHERE id=%s
                        """,
                        (duration_seconds, str(exc), session_id),
                    )

            if self.audit_logger is not None:
                self.audit_logger.log_pipeline_event(
                    event_type="ERROR",
                    module="crawl-custom",
                    data_count=None,
                    duration_ms=int(max(0, (time.time() - started) * 1000)),
                    error=exc,
                    level="ERROR",
                )
            raise
        finally:
            if conn is not None:
                conn.close()

    def get_session_stats(self, session_id: int) -> Dict[str, object]:
        set_settings_for_retry(self.settings)
        conn = get_mysql_connection(self.settings)
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_url, page_count, ip_count, proxy_count, status,
                           started_at, completed_at, duration_seconds, error_message
                    FROM crawl_session
                    WHERE id=%s
                    """,
                    (session_id,),
                )
                session_row = cursor.fetchone()
                if not session_row:
                    raise ValueError(f"crawl session not found: {session_id}")

                cursor.execute(
                    """
                    SELECT COUNT(1),
                           COALESCE(SUM(extracted_proxies), 0),
                           COALESCE(AVG(extraction_confidence), 0)
                    FROM crawl_page_log
                    WHERE session_id=%s
                    """,
                    (session_id,),
                )
                page_row = cursor.fetchone() or (0, 0, 0)

                cursor.execute(
                    """
                    SELECT COUNT(1), COALESCE(SUM(cost_usd), 0)
                    FROM llm_call_log
                    WHERE session_id=%s
                    """,
                    (session_id,),
                )
                llm_row = cursor.fetchone() or (0, 0)

                cursor.execute(
                    """
                    SELECT COUNT(1)
                    FROM proxy_review_queue
                    WHERE session_id=%s AND review_status='pending'
                    """,
                    (session_id,),
                )
                review_row = cursor.fetchone() or (0,)

            return {
                "session_id": int(session_row[0]),
                "url": session_row[1],
                "page_count": int(session_row[2]),
                "ip_count": int(session_row[3]),
                "proxy_count": int(session_row[4]),
                "status": session_row[5],
                "started_at": session_row[6],
                "completed_at": session_row[7],
                "duration_seconds": session_row[8],
                "error_message": session_row[9],
                "page_logs": int(page_row[0]),
                "page_extracted_total": int(page_row[1]),
                "avg_extraction_confidence": float(page_row[2]),
                "llm_calls": int(llm_row[0]),
                "llm_cost_usd": float(llm_row[1]),
                "review_pending_count": int(review_row[0]),
            }
        finally:
            conn.close()

    def resume_from_checkpoint(self, session_id: int) -> DynamicCrawlResult:
        set_settings_for_retry(self.settings)
        conn = get_mysql_connection(self.settings)
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_url, max_pages, use_ai_fallback
                    FROM crawl_session
                    WHERE id=%s
                    """,
                    (session_id,),
                )
                session_row = cursor.fetchone()
                if not session_row:
                    raise ValueError(f"crawl session not found: {session_id}")

                user_url = str(session_row[0])
                max_pages = int(session_row[1])
                use_ai_fallback = bool(session_row[2])

                cursor.execute(
                    """
                    SELECT page_number, next_page_url
                    FROM crawl_page_log
                    WHERE session_id=%s
                    ORDER BY page_number DESC
                    LIMIT 1
                    """,
                    (session_id,),
                )
                last_page = cursor.fetchone()
        finally:
            conn.close()

        if not last_page:
            return self.crawl(
                url=user_url,
                max_pages=max_pages,
                use_ai=use_ai_fallback,
                no_store=False,
                verbose=False,
            )

        last_page_number = int(last_page[0])
        next_page_url = last_page[1]
        start_url = str(next_page_url) if next_page_url else user_url
        remaining_pages = max(1, max_pages - last_page_number)

        return self.crawl(
            url=start_url,
            max_pages=remaining_pages,
            use_ai=use_ai_fallback,
            no_store=False,
            verbose=False,
        )


def crawl_custom_url(
    settings: Settings,
    url: str,
    max_pages: int = 1,
    use_ai: bool = False,
    no_store: bool = False,
    verbose: bool = False,
    render_js: bool = False,
) -> DynamicCrawlResult:
    crawler = DynamicCrawler(settings)
    return crawler.crawl(
        url=url,
        max_pages=max_pages,
        use_ai=use_ai,
        no_store=no_store,
        verbose=verbose,
        render_js=render_js,
    )
