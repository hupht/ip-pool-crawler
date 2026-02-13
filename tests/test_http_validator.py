from unittest.mock import patch

import requests

from crawler.http_validator import HTTPValidationResult, HTTPValidator


class _DummyResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_validate_with_http_success():
    with patch("crawler.http_validator.requests.get", return_value=_DummyResponse(200)):
        result = HTTPValidator.validate_with_http("1.2.3.4", 8080, "http", timeout=2)

    assert isinstance(result, HTTPValidationResult)
    assert result.is_reachable is True
    assert result.protocol_verified is True
    assert result.status_code == 200


def test_validate_with_http_non_2xx():
    with patch("crawler.http_validator.requests.get", return_value=_DummyResponse(503)):
        result = HTTPValidator.validate_with_http("1.2.3.4", 8080, "https", timeout=2)

    assert result.is_reachable is False
    assert result.protocol_verified is True
    assert result.status_code == 503


def test_validate_with_http_request_error():
    with patch("crawler.http_validator.requests.get", side_effect=requests.Timeout("timeout")):
        result = HTTPValidator.validate_with_http("1.2.3.4", 8080, "http", timeout=1)

    assert result.is_reachable is False
    assert result.protocol_verified is False
    assert result.status_code is None
    assert result.errors


def test_validate_with_http_socks5_protocol():
    with patch("crawler.http_validator.requests.get", return_value=_DummyResponse(200)):
        result = HTTPValidator.validate_with_http("1.2.3.4", 1080, "socks5", timeout=2)

    assert result.is_reachable is True
    assert result.protocol_verified is True


def test_validate_with_http_unsupported_protocol():
    result = HTTPValidator.validate_with_http("1.2.3.4", 21, "ftp", timeout=2)

    assert result.is_reachable is False
    assert result.protocol_verified is False
    assert "unsupported protocol" in result.errors[0]


def test_batch_validate_returns_results():
    proxies = [
        {"ip": "1.2.3.4", "port": 8080, "protocol": "http"},
        {"ip": "5.6.7.8", "port": 1080, "protocol": "socks4"},
    ]
    with patch("crawler.http_validator.requests.get", return_value=_DummyResponse(200)):
        results = HTTPValidator.batch_validate(proxies, timeout=2)

    assert len(results) == 2
    assert all(isinstance(item, HTTPValidationResult) for item in results)
    assert all(item.is_reachable for item in results)
