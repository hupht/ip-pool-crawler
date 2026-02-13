from crawler.pipeline import normalize_record
import crawler.pipeline as pipeline
from crawler.http_validator import HTTPValidationResult
from crawler.sources import Source
from crawler.config import Settings


def test_normalize_record_min_fields():
    record = normalize_record({"ip": "1.1.1.1", "port": "80"})
    assert record["ip"] == "1.1.1.1"
    assert record["port"] == 80


def test_check_record_uses_http_validator_result(monkeypatch):
    def fake_validate_with_http(ip, port, protocol, timeout):
        return HTTPValidationResult(
            is_reachable=True,
            status_code=200,
            response_time_ms=123,
            protocol_verified=True,
            errors=[],
        )

    monkeypatch.setattr(
        pipeline.HTTPValidator,
        "validate_with_http",
        fake_validate_with_http,
    )

    success, latency = pipeline._check_record(
        {"ip": "1.2.3.4", "port": 8080, "protocol": "http"},
        timeout=2,
    )

    assert success is True
    assert latency == 123


def test_check_record_fallback_to_tcp(monkeypatch):
    def fake_validate_with_http(ip, port, protocol, timeout):
        return HTTPValidationResult(
            is_reachable=False,
            status_code=None,
            response_time_ms=0,
            protocol_verified=False,
            errors=["timeout"],
        )

    def fake_tcp_check(ip, port, timeout):
        return True, 88

    monkeypatch.setattr(
        pipeline.HTTPValidator,
        "validate_with_http",
        fake_validate_with_http,
    )
    monkeypatch.setattr(pipeline, "tcp_check", fake_tcp_check)

    success, latency = pipeline._check_record(
        {"ip": "1.2.3.4", "port": 8080, "protocol": "socks5"},
        timeout=2,
    )

    assert success is True
    assert latency == 88


def test_run_once_quick_test_stops_after_first_success_source(monkeypatch):
    class DummyConn:
        def close(self):
            return None

    settings = Settings.from_env()

    fetch_calls = []

    def fake_get_sources():
        return [
            Source(name="source-a", url="http://a", parser_key="a"),
            Source(name="source-b", url="http://b", parser_key="b"),
        ]

    def fake_fetch_and_parse(source, _settings):
        fetch_calls.append(source.name)
        if source.name == "source-a":
            return [{"ip": "1.2.3.4", "port": 8080, "protocol": "http"}]
        return [{"ip": "5.6.7.8", "port": 9090, "protocol": "https"}]

    def fake_upsert_source(_conn, _name, _url, _parser_key):
        return 1

    monkeypatch.setattr(pipeline, "set_settings_for_retry", lambda _settings: None)
    monkeypatch.setattr(pipeline, "get_sources", fake_get_sources)
    monkeypatch.setattr(pipeline, "get_mysql_connection", lambda _settings: DummyConn())
    monkeypatch.setattr(pipeline, "get_redis_client", lambda _settings: object())
    monkeypatch.setattr(pipeline, "upsert_source", fake_upsert_source)
    monkeypatch.setattr(pipeline, "_fetch_and_parse", fake_fetch_and_parse)
    monkeypatch.setattr(pipeline, "_check_record", lambda record, timeout: (True, 10))
    monkeypatch.setattr(pipeline, "upsert_proxy", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "update_proxy_check", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "upsert_redis_pool", lambda *args, **kwargs: None)

    pipeline.run_once(settings, quick_test=True, quick_record_limit=1)

    assert fetch_calls == ["source-a"]


def test_parse_by_source_unknown_parser_returns_empty():
    source = Source(name="x", url="http://x", parser_key="unknown")
    assert pipeline.parse_by_source(source, "raw") == []


def test_normalize_records_filters_invalid_items():
    records = [
        {"ip": "1.1.1.1", "port": "80", "protocol": "http"},
        {"ip": "", "port": 8080, "protocol": "http"},
    ]

    normalized = list(pipeline._normalize_records(records))

    assert len(normalized) == 1
    assert normalized[0]["ip"] == "1.1.1.1"


def test_check_record_exception_returns_false(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline.HTTPValidator, "validate_with_http", _raise)

    success, latency = pipeline._check_record({"ip": "1.2.3.4", "port": 80, "protocol": "http"}, timeout=1)

    assert success is False
    assert latency == 0


def test_run_once_non_quick_handles_fetch_exception(monkeypatch):
    class DummyConn:
        def close(self):
            return None

    settings = Settings.from_env()
    settings.source_workers = 1
    settings.validate_workers = 1

    def fake_get_sources():
        return [Source(name="source-a", url="http://a", parser_key="a")]

    monkeypatch.setattr(pipeline, "set_settings_for_retry", lambda _settings: None)
    monkeypatch.setattr(pipeline, "get_sources", fake_get_sources)
    monkeypatch.setattr(pipeline, "get_mysql_connection", lambda _settings: DummyConn())
    monkeypatch.setattr(pipeline, "get_redis_client", lambda _settings: object())
    monkeypatch.setattr(pipeline, "upsert_source", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(pipeline, "_fetch_and_parse", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fetch failed")))

    called = {"upsert_proxy": 0, "update": 0, "redis": 0}
    monkeypatch.setattr(pipeline, "upsert_proxy", lambda *args, **kwargs: called.__setitem__("upsert_proxy", called["upsert_proxy"] + 1))
    monkeypatch.setattr(pipeline, "update_proxy_check", lambda *args, **kwargs: called.__setitem__("update", called["update"] + 1))
    monkeypatch.setattr(pipeline, "upsert_redis_pool", lambda *args, **kwargs: called.__setitem__("redis", called["redis"] + 1))

    pipeline.run_once(settings, quick_test=False)

    assert called["upsert_proxy"] == 0
    assert called["update"] == 0
    assert called["redis"] == 0
