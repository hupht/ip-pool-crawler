import json

from crawler.config import Settings


def test_get_proxy_cli_defaults(monkeypatch, capsys):
    from tools import get_proxy

    expected = {
        "status": "ok",
        "data": {
            "ip": "1.1.1.1",
            "port": 80,
            "protocol": "http",
            "country": "US",
            "latency_ms": 12,
        },
    }

    monkeypatch.setattr(get_proxy, "pick_proxies", lambda *_args, **_kwargs: expected)

    exit_code = get_proxy.run([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == expected


def test_get_proxy_cli_passes_args(monkeypatch):
    from tools import get_proxy

    called = {}

    def fake_pick(settings, **kwargs):
        assert isinstance(settings, Settings)
        called.update(kwargs)
        return {"status": "ok", "data": None}

    monkeypatch.setattr(get_proxy, "pick_proxies", fake_pick)

    exit_code = get_proxy.run(
        [
            "--protocol",
            "http,https",
            "--country",
            "US,CN",
            "--count",
            "2",
            "--no-check",
            "--check-url",
            "https://example.com",
        ]
    )

    assert exit_code == 0
    assert called["protocols"] == ["http", "https"]
    assert called["countries"] == ["US", "CN"]
    assert called["count"] == 2
    assert called["require_check"] is False
    assert called["check_url"] == "https://example.com"
