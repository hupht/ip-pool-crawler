import requests

from crawler.config import Settings
from crawler.fetcher import fetch_source
from crawler.sources import Source


def test_fetch_source_returns_empty_on_error(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise requests.exceptions.SSLError("boom")

    monkeypatch.setattr(requests, "get", _raise)

    settings = Settings.from_env()
    source = Source(name="x", url="https://example.com", parser_key="x")
    body, status = fetch_source(source, settings)

    assert body == ""
    assert status == 0


def test_fetch_source_returns_empty_on_timeout(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise TimeoutError("timeout")

    monkeypatch.setattr(requests, "get", _raise)

    settings = Settings.from_env()
    source = Source(name="x", url="https://example.com", parser_key="x")
    body, status = fetch_source(source, settings)

    assert body == ""
    assert status == 0


