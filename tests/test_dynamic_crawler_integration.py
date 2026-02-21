from crawler.config import Settings
from crawler.dynamic_crawler import crawl_custom_url
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _DummyResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


def test_crawl_custom_url_minimal_integration(monkeypatch):
    settings = Settings.from_env()
    settings.use_ai_fallback = False

    html = """
    <html><body>
      1.2.3.4:8080:http
      <a href=\"?page=2\">Next</a>
    </body></html>
    """

    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(html),
    )

    result = crawl_custom_url(
        settings=settings,
        url="https://example.com/proxy",
        max_pages=1,
        use_ai=False,
        no_store=True,
        verbose=False,
    )

    assert result.url == "https://example.com/proxy"
    assert result.pages_crawled == 1
    assert result.extracted >= 1
    assert result.valid >= 1
    assert result.stored == 0


def test_crawl_custom_url_multi_page_integration(monkeypatch):
    settings = Settings.from_env()
    settings.use_ai_fallback = False

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

    result = crawl_custom_url(
        settings=settings,
        url="https://example.com/proxy",
        max_pages=3,
        use_ai=False,
        no_store=True,
        verbose=False,
    )

    assert result.pages_crawled == 2
    assert result.valid >= 2


def test_crawl_custom_url_real_http_server():
    settings = Settings.from_env()
    settings.use_ai_fallback = False

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path in ["/", "/?page=1"]:
                body = """
                <html><body>
                  1.2.3.4:8080:http
                  <a href='/?page=2'>Next</a>
                </body></html>
                """
            else:
                body = """
                <html><body>
                  5.6.7.8:9090:https
                </body></html>
                """
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):  # noqa: A003
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        url = f"http://127.0.0.1:{server.server_port}/?page=1"
        result = crawl_custom_url(
            settings=settings,
            url=url,
            max_pages=2,
            use_ai=False,
            no_store=True,
            verbose=False,
        )
        assert result.pages_crawled == 2
        assert result.valid >= 2
    finally:
        server.shutdown()
        server.server_close()


def test_crawl_custom_data_flow_with_storage(monkeypatch):
    settings = Settings.from_env()
    settings.use_ai_fallback = False

    class _FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params=None):
            return None

        def fetchone(self):
            return (0,)

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    calls = {
        "insert_crawl_session": 0,
        "insert_page_log": 0,
        "upsert_proxy": 0,
    }

    monkeypatch.setattr("crawler.dynamic_crawler.get_mysql_connection", lambda _settings: _FakeConn())
    monkeypatch.setattr("crawler.dynamic_crawler.upsert_source", lambda conn, name, url, parser_key: 1)
    monkeypatch.setattr(
        "crawler.dynamic_crawler.insert_crawl_session",
        lambda conn, session: calls.__setitem__("insert_crawl_session", calls["insert_crawl_session"] + 1) or 100,
    )
    monkeypatch.setattr(
        "crawler.dynamic_crawler.insert_page_log",
        lambda conn, log: calls.__setitem__("insert_page_log", calls["insert_page_log"] + 1) or 200,
    )
    monkeypatch.setattr(
        "crawler.dynamic_crawler.upsert_proxy",
        lambda *args, **kwargs: calls.__setitem__("upsert_proxy", calls["upsert_proxy"] + 1),
    )

    html = "<html><body>1.2.3.4:8080:http</body></html>"
    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(html),
    )

    result = crawl_custom_url(
        settings=settings,
        url="https://example.com/proxy",
        max_pages=1,
        use_ai=False,
        no_store=False,
        verbose=False,
    )

    assert result.stored >= 1
    assert calls["insert_crawl_session"] == 1
    assert calls["insert_page_log"] >= 1
    assert calls["upsert_proxy"] >= 1


def test_crawl_custom_ai_review_and_llm_log(monkeypatch):
    settings = Settings.from_env()

    class _FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params=None):
            return None

        def fetchone(self):
            return (0,)

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    calls = {"review": 0, "llm_log": 0}
    monkeypatch.setattr("crawler.dynamic_crawler.get_mysql_connection", lambda _settings: _FakeConn())
    monkeypatch.setattr("crawler.dynamic_crawler.upsert_source", lambda conn, name, url, parser_key: 1)
    monkeypatch.setattr("crawler.dynamic_crawler.insert_crawl_session", lambda conn, session: 11)
    monkeypatch.setattr("crawler.dynamic_crawler.insert_page_log", lambda conn, log: 22)
    monkeypatch.setattr("crawler.dynamic_crawler.check_duplicate", lambda *args, **kwargs: False)
    monkeypatch.setattr("crawler.dynamic_crawler.upsert_proxy", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "crawler.dynamic_crawler.insert_review_queue_item",
        lambda conn, data: calls.__setitem__("review", calls["review"] + 1) or 1,
    )
    monkeypatch.setattr(
        "crawler.dynamic_crawler.insert_llm_call_log",
        lambda conn, log: calls.__setitem__("llm_log", calls["llm_log"] + 1) or 1,
    )

    def fake_process(self, html, context):
        return (
            [{"ip": "1.2.3.4", "port": 8080, "protocol": "http", "confidence": 0.9}],
            [{"ip": "2.2.2.2", "port": 8081, "protocol": "http", "review_reason": "low_confidence"}],
            {
                "ai_called": True,
                "ai_reason": "failed_parse",
                "ai_result": {"proxies": [{"ip": "1.2.3.4", "port": 8080}], "tokens": {"input": 1, "output": 1, "total": 2}},
            },
        )

    monkeypatch.setattr("crawler.error_handler.ErrorHandler.process_page_with_meta", fake_process)
    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse("<html><body>stub</body></html>"),
    )

    crawl_custom_url(
        settings=settings,
        url="https://example.com/proxy",
        max_pages=1,
        use_ai=True,
        no_store=False,
        verbose=False,
    )

    assert calls["review"] >= 1
    assert calls["llm_log"] >= 1


def test_crawl_custom_performance_multi_page(monkeypatch):
    settings = Settings.from_env()
    settings.use_ai_fallback = False
    settings.max_pages_no_new_ip = 50

    pages = {}
    for i in range(1, 21):
        next_link = f"<a href='?page={i+1}'>next</a>" if i < 20 else ""
        pages[f"https://example.com/proxy?page={i}"] = (
            f"<html><body>{i}.{i}.{i}.{i}:80:http {next_link}</body></html>"
        )

    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(pages[url]),
    )

    started = time.perf_counter()
    result = crawl_custom_url(
        settings=settings,
        url="https://example.com/proxy?page=1",
        max_pages=20,
        use_ai=False,
        no_store=True,
        verbose=False,
    )
    elapsed = time.perf_counter() - started

    assert result.pages_crawled == 20
    assert elapsed < 2.5
