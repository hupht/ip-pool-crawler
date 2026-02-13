from crawler.config import Settings
from crawler.proxy_picker import allocate_protocols, parse_redis_key, pick_proxies


def test_parse_redis_key():
    result = parse_redis_key("1.2.3.4:8080:http")
    assert result == {
        "ip": "1.2.3.4",
        "port": 8080,
        "protocol": "http",
    }


def test_allocate_protocols_defaults_balanced():
    result = allocate_protocols(None, 3)
    assert result == ["http", "https", "http"]


def test_pick_proxies_default_one_no_check(monkeypatch):
    from crawler import proxy_picker

    settings = Settings()
    candidate = {"ip": "1.1.1.1", "port": 80, "protocol": "http", "country": None, "latency_ms": 10}

    monkeypatch.setattr(proxy_picker, "_fetch_redis_candidates", lambda *_args, **_kwargs: [candidate])
    monkeypatch.setattr(proxy_picker, "_fetch_mysql_candidates", lambda *_args, **_kwargs: [])

    result = pick_proxies(
        settings,
        count=1,
        require_check=False,
        redis_client=object(),
        mysql_conn=object(),
    )

    assert result["status"] == "ok"
    assert result["data"]["ip"] == "1.1.1.1"


def test_pick_proxies_country_fallback(monkeypatch):
    from crawler import proxy_picker

    settings = Settings()
    candidate = {"ip": "2.2.2.2", "port": 443, "protocol": "https", "country": None, "latency_ms": 20}

    monkeypatch.setattr(proxy_picker, "_fetch_redis_candidates", lambda *_args, **_kwargs: [candidate])
    monkeypatch.setattr(proxy_picker, "_filter_candidates_by_countries", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(proxy_picker, "_fetch_mysql_candidates", lambda *_args, **_kwargs: [])

    result = pick_proxies(
        settings,
        countries=["US"],
        count=1,
        require_check=False,
        redis_client=object(),
        mysql_conn=object(),
    )

    assert result["status"] == "not_found_country_fallback"
    assert result["data"]["ip"] == "2.2.2.2"
