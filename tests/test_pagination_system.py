from crawler.config import Settings
from crawler.dynamic_crawler import crawl_custom_url
from crawler.dynamic_crawler import DynamicCrawlResult, DynamicCrawler


class _DummyResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


def test_pagination_system_respects_max_pages(monkeypatch):
    settings = Settings.from_env()

    pages = {
        "https://example.com/proxy": """
        <html><body>
          1.1.1.1:8080:http
          <a href='?page=2'>next</a>
        </body></html>
        """,
        "https://example.com/proxy?page=2": """
        <html><body>
          2.2.2.2:8080:http
          <a href='?page=3'>next</a>
        </body></html>
        """,
        "https://example.com/proxy?page=3": """
        <html><body>
          3.3.3.3:8080:http
        </body></html>
        """,
    }

    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(pages[url]),
    )

    result = crawl_custom_url(
        settings=settings,
        url="https://example.com/proxy",
        max_pages=2,
        use_ai=False,
        no_store=True,
        verbose=False,
    )

    assert result.pages_crawled == 2
    assert result.valid >= 2


def test_pagination_system_stops_on_no_new_ip_streak(monkeypatch):
    settings = Settings.from_env()
    settings.max_pages_no_new_ip = 2

    pages = {
        "https://example.com/proxy": """
        <html><body>
          9.9.9.9:8080:http
          <a href='?page=2'>next</a>
        </body></html>
        """,
        "https://example.com/proxy?page=2": """
        <html><body>
          9.9.9.9:8080:http
          <a href='?page=3'>next</a>
        </body></html>
        """,
        "https://example.com/proxy?page=3": """
        <html><body>
          9.9.9.9:8080:http
          <a href='?page=4'>next</a>
        </body></html>
        """,
        "https://example.com/proxy?page=4": """
        <html><body>
          9.9.9.9:8080:http
        </body></html>
        """,
    }

    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(pages[url]),
    )

    result = crawl_custom_url(
        settings=settings,
        url="https://example.com/proxy",
        max_pages=10,
        use_ai=False,
        no_store=True,
        verbose=False,
    )

    assert result.pages_crawled == 3
    assert result.valid >= 1


def test_pagination_system_cross_page_dedup(monkeypatch):
    settings = Settings.from_env()

    pages = {
        "https://example.com/proxy": """
        <html><body>
          8.8.8.8:8080:http
          <a href='?page=2'>next</a>
        </body></html>
        """,
        "https://example.com/proxy?page=2": """
        <html><body>
          8.8.8.8:8080:http
        </body></html>
        """,
    }

    monkeypatch.setattr(
        "crawler.dynamic_crawler.requests.get",
        lambda url, headers, timeout: _DummyResponse(pages[url]),
    )

    result = crawl_custom_url(
        settings=settings,
        url="https://example.com/proxy",
        max_pages=3,
        use_ai=False,
        no_store=True,
        verbose=False,
    )

    assert result.pages_crawled == 2
    assert result.valid == 1


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


def test_pagination_system_checkpoint_resume_uses_recorded_next_url(monkeypatch):
    settings = Settings.from_env()
    crawler = DynamicCrawler(settings)

    session_row = ("https://example.com/proxy", 6, 0)
    last_page_row = (2, "https://example.com/proxy?page=3")

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

    crawler.resume_from_checkpoint(123)

    assert captured["url"] == "https://example.com/proxy?page=3"
    assert captured["max_pages"] == 4
    assert captured["use_ai"] is False
    assert captured["no_store"] is False
