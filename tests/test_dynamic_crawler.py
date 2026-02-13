import requests

from crawler.config import Settings
from crawler.dynamic_crawler import DynamicCrawlResult, DynamicCrawler


class _DummyResponse:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        return None


def test_dynamic_crawler_single_page(monkeypatch):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    html_page = """
    <html><body>
      1.2.3.4:8080:http
    </body></html>
    """

    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(html_page),
    )

    result = crawler.crawl(
        url="https://example.com/proxy",
        max_pages=1,
        use_ai=False,
        no_store=True,
        verbose=False,
    )

    assert result.pages_crawled == 1
    assert result.extracted >= 1
    assert result.valid >= 1


def test_dynamic_crawler_multi_page_with_next_link(monkeypatch):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    pages = {
        "https://example.com/proxy": """
        <html><body>
          1.2.3.4:8080:http
          <a href=\"?page=2\">Next</a>
        </body></html>
        """,
        "https://example.com/proxy?page=2": """
        <html><body>
          5.6.7.8:9090:https
        </body></html>
        """,
    }

    def fake_get(url, headers, timeout):
        return _DummyResponse(pages[url])

    monkeypatch.setattr("crawler.dynamic_crawler.requests.get", fake_get)

    result = crawler.crawl(
        url="https://example.com/proxy",
        max_pages=3,
        use_ai=False,
        no_store=True,
        verbose=False,
    )

    assert result.pages_crawled == 2
    assert result.extracted >= 2
    assert result.valid >= 2


def test_dynamic_crawler_respects_max_pages(monkeypatch):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    pages = {
        "https://example.com/proxy": """
        <html><body>
          1.2.3.4:8080:http
          <a href=\"?page=2\">Next</a>
        </body></html>
        """,
        "https://example.com/proxy?page=2": """
        <html><body>
          5.6.7.8:9090:https
        </body></html>
        """,
    }

    def fake_get(url, headers, timeout):
        return _DummyResponse(pages[url])

    monkeypatch.setattr("crawler.dynamic_crawler.requests.get", fake_get)

    result = crawler.crawl(
        url="https://example.com/proxy",
        max_pages=1,
        use_ai=False,
        no_store=True,
        verbose=False,
    )

    assert result.pages_crawled == 1


def test_dynamic_crawler_use_ai_path(monkeypatch):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    html_page = "<html><body>no proxy here</body></html>"
    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(html_page),
    )

    called = {"n": 0}

    def fake_process_page_with_meta(self, html, context):
        called["n"] += 1
        return (
            [{"ip": "1.2.3.4", "port": 8080, "protocol": "http", "confidence": 0.9}],
            [],
            {"ai_called": True, "ai_reason": "failed_parse", "ai_result": {"proxies": []}},
        )

    monkeypatch.setattr(
        "crawler.error_handler.ErrorHandler.process_page_with_meta",
        fake_process_page_with_meta,
    )

    result = crawler.crawl(
        url="https://example.com/proxy",
        max_pages=1,
        use_ai=True,
        no_store=True,
        verbose=False,
    )

    assert called["n"] == 1
    assert result.valid >= 1


def test_dynamic_crawler_verbose_prints_progress(monkeypatch, capsys):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    html_page = """
    <html><body>
      1.2.3.4:8080:http
    </body></html>
    """

    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(html_page),
    )

    crawler.crawl(
        url="https://example.com/proxy",
        max_pages=1,
        use_ai=False,
        no_store=True,
        verbose=True,
    )

    output = capsys.readouterr().out
    assert "crawl-custom start" in output
    assert "crawl-custom fetching page=1" in output
    assert "crawl-custom page=1" in output


def test_dynamic_crawler_writes_failed_page_log_on_fetch_error(monkeypatch):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    class _FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params=None):
            return None

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    calls = {"insert_page_log": 0}
    monkeypatch.setattr("crawler.dynamic_crawler.get_mysql_connection", lambda _settings: _FakeConn())
    monkeypatch.setattr("crawler.dynamic_crawler.insert_crawl_session", lambda conn, data: 1)
    monkeypatch.setattr("crawler.dynamic_crawler.upsert_source", lambda conn, name, url, parser: 1)
    monkeypatch.setattr(
        "crawler.dynamic_crawler.insert_page_log",
        lambda conn, data: calls.__setitem__("insert_page_log", calls["insert_page_log"] + 1) or 1,
    )
    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.HTTPError("boom")),
    )

    try:
        crawler.crawl(
            url="https://example.com/proxy",
            max_pages=1,
            use_ai=False,
            no_store=False,
            verbose=False,
        )
        assert False
    except requests.HTTPError:
        pass

    assert calls["insert_page_log"] >= 1


def test_dynamic_crawler_calls_audit_logger(monkeypatch):
    settings = Settings.from_env()

    class _Logger:
        def __init__(self):
            self.pipeline_events = 0
            self.http_events = 0

        def log_pipeline_event(self, **kwargs):
            self.pipeline_events += 1

        def log_http_request(self, **kwargs):
            self.http_events += 1

    fake_logger = _Logger()
    monkeypatch.setattr("crawler.dynamic_crawler.get_logger", lambda _settings: fake_logger)
    crawler = DynamicCrawler(settings)

    html_page = "<html><body>1.2.3.4:8080:http</body></html>"
    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(html_page),
    )

    crawler.crawl(
        url="https://example.com/proxy",
        max_pages=1,
        use_ai=False,
        no_store=True,
        verbose=False,
    )

    assert fake_logger.http_events >= 1
    assert fake_logger.pipeline_events >= 2


def test_dynamic_crawler_render_js_path(monkeypatch):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    called = {"n": 0}

    def fake_fetch(url, user_agent, timeout_seconds, wait_selector=None):
        called["n"] += 1
        return "<html><body>1.2.3.4:8080:http</body></html>"

    monkeypatch.setattr("crawler.dynamic_crawler.fetch_page_with_playwright", fake_fetch)

    result = crawler.crawl(
        url="https://example.com/proxy",
        max_pages=1,
        use_ai=False,
        no_store=True,
        verbose=False,
        render_js=True,
    )

    assert called["n"] == 1
    assert result.valid >= 1


class _FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        return None

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)

    def close(self):
        return None


def test_get_session_stats(monkeypatch):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    session_row = (10, "https://example.com/proxy", 3, 30, 20, "completed", None, None, 12, None)
    page_row = (3, 28, 0.86)
    llm_row = (2, 0.0312)
    review_row = (4,)

    monkeypatch.setattr(
        "crawler.dynamic_crawler.get_mysql_connection",
        lambda _settings: _FakeConnection([session_row, page_row, llm_row, review_row]),
    )

    stats = crawler.get_session_stats(10)

    assert stats["session_id"] == 10
    assert stats["url"] == "https://example.com/proxy"
    assert stats["page_count"] == 3
    assert stats["proxy_count"] == 20
    assert stats["page_logs"] == 3
    assert stats["page_extracted_total"] == 28
    assert stats["avg_extraction_confidence"] == 0.86
    assert stats["llm_calls"] == 2
    assert stats["llm_cost_usd"] == 0.0312
    assert stats["review_pending_count"] == 4


def test_resume_from_checkpoint_uses_next_page(monkeypatch):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    session_row = ("https://example.com/proxy", 8, 1)
    last_page_row = (3, "https://example.com/proxy?page=4")

    monkeypatch.setattr(
        "crawler.dynamic_crawler.get_mysql_connection",
        lambda _settings: _FakeConnection([session_row, last_page_row]),
    )

    captured = {}

    def fake_crawl(url, max_pages, use_ai, no_store, verbose):
        captured["url"] = url
        captured["max_pages"] = max_pages
        captured["use_ai"] = use_ai
        captured["no_store"] = no_store
        return DynamicCrawlResult(
            url=url,
            pages_crawled=0,
            extracted=0,
            valid=0,
            invalid=0,
            stored=0,
            session_id=None,
        )

    monkeypatch.setattr(crawler, "crawl", fake_crawl)

    crawler.resume_from_checkpoint(1)

    assert captured["url"] == "https://example.com/proxy?page=4"
    assert captured["max_pages"] == 5
    assert captured["use_ai"] is True
    assert captured["no_store"] is False
