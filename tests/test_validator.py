from types import SimpleNamespace

from crawler.validator import Validator, score_proxy, tcp_check


class _DummySocket:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_tcp_check_success(monkeypatch):
    monkeypatch.setattr("crawler.validator.socket.create_connection", lambda *_args, **_kwargs: _DummySocket())
    is_alive, latency_ms = tcp_check("127.0.0.1", 80, timeout=1)

    assert is_alive is True
    assert latency_ms >= 0


def test_tcp_check_failure(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise OSError("connect failed")

    monkeypatch.setattr("crawler.validator.socket.create_connection", _raise)

    is_alive, latency_ms = tcp_check("127.0.0.1", 80, timeout=1)

    assert is_alive is False
    assert latency_ms == 0


def test_score_proxy_prefers_lower_latency():
    s1 = score_proxy(latency_ms=100, success=True)
    s2 = score_proxy(latency_ms=500, success=True)
    assert s1 > s2


def test_score_proxy_failure_is_zero():
    assert score_proxy(latency_ms=10, success=False) == 0


def test_validator_validate_ip_port():
    validator = Validator()

    assert validator.validate_ip("1.2.3.4") is True
    assert validator.validate_ip("999.2.3.4") is False

    assert validator.validate_port(8080) is True
    assert validator.validate_port(0) is False


def test_validator_validate_table_structure():
    validator = Validator()
    table_ok = SimpleNamespace(headers=["IP", "Port"], rows=[["1.2.3.4", "8080"]])
    table_bad = SimpleNamespace(headers=["IP", "Port"], rows=[["1.2.3.4", "8080", "extra", "x"]])

    ok, reason_ok = validator.validate_table_structure(table_ok)
    bad, reason_bad = validator.validate_table_structure(table_bad)

    assert ok is True
    assert reason_ok == "ok"
    assert bad is False
    assert "mismatch" in reason_bad


def test_validator_validate_page_coverage():
    validator = Validator()

    assert validator.validate_page_coverage([{"id": 1}, {"id": 2}], expected=4) == 0.5
    assert validator.validate_page_coverage([], expected=0) == 1.0


def test_validator_mark_suspicious_data():
    validator = Validator(suspicious_threshold=0.8)
    flagged = validator.mark_suspicious_data({"ip": "1.2.3.4", "port": 80, "confidence": 0.2})
    clean = validator.mark_suspicious_data({"ip": "1.2.3.4", "port": 80, "confidence": 0.95})

    assert flagged["is_suspicious"] is True
    assert "low_confidence" in flagged["suspicious_reasons"]
    assert clean["is_suspicious"] is False
