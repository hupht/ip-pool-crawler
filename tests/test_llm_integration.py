import json

from crawler.error_handler import ErrorHandler
from crawler.llm_config import LLMConfig


class _DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"http {self.status_code}")

    def json(self):
        return self._payload


def _build_enabled_config() -> LLMConfig:
    return LLMConfig(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        enabled=True,
        cache_enabled=True,
        trigger_on_failed_parse=True,
    )


def test_integration_llm_call_with_cache_hit(monkeypatch):
    cfg = _build_enabled_config()
    handler = ErrorHandler(llm_config=cfg)

    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "proxies": [
                                {"ip": "1.2.3.4", "port": 8080, "protocol": "http", "confidence": 0.9}
                            ]
                        }
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 200, "total_tokens": 1400},
    }

    request_count = {"n": 0}

    def fake_post(*args, **kwargs):
        request_count["n"] += 1
        return _DummyResponse(payload)

    monkeypatch.setattr("crawler.llm_caller.requests.post", fake_post)

    html = "<html><body>unparseable page</body></html>"
    context = {"reason": "failed_parse", "url": "https://example.com"}

    first = handler.handle_extraction_failure(html=html, context=context)
    second = handler.handle_extraction_failure(html=html, context=context)

    assert request_count["n"] == 1
    assert len(first["proxies"]) == 1
    assert first["tokens"]["total"] == 1400
    assert first["cost_usd"] > 0
    assert second.get("cache_hit") is True


def test_integration_process_page_failed_parse_uses_llm(monkeypatch):
    cfg = _build_enabled_config()
    handler = ErrorHandler(llm_config=cfg)

    monkeypatch.setattr(
        "crawler.error_handler.UniversalParser.extract_all",
        lambda html: ([], {"from_tables": 0, "total_extracted": 0}),
    )

    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "proxies": [
                                {"ip": "8.8.8.8", "port": 8080, "protocol": "http", "confidence": 0.95}
                            ]
                        }
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
    }

    monkeypatch.setattr("crawler.llm_caller.requests.post", lambda *args, **kwargs: _DummyResponse(payload))

    valid, review = handler.process_page("<html></html>", context={"url": "https://example.com/list"})

    assert len(valid) == 1
    assert valid[0]["source"] == "ai"
    assert valid[0]["ip"] == "8.8.8.8"
    assert len(review) == 0


def test_integration_llm_parse_failure_returns_empty_proxies(monkeypatch):
    cfg = _build_enabled_config()
    handler = ErrorHandler(llm_config=cfg)

    payload = {
        "choices": [{"message": {"content": "not a json response"}}],
        "usage": {"prompt_tokens": 500, "completion_tokens": 50, "total_tokens": 550},
    }

    monkeypatch.setattr("crawler.llm_caller.requests.post", lambda *args, **kwargs: _DummyResponse(payload))

    result = handler.handle_extraction_failure("<html>broken</html>", context={"reason": "failed_parse"})

    assert result["proxies"] == []
    assert result["tokens"]["total"] == 550
    assert "cost_usd" in result


def test_integration_cost_control_blocks_followup_calls(monkeypatch):
    cfg = LLMConfig(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        enabled=True,
        cache_enabled=False,
        trigger_on_failed_parse=True,
        cost_limit_usd=0.0002,
    )
    handler = ErrorHandler(llm_config=cfg)

    request_count = {"n": 0}

    def fake_post(*args, **kwargs):
        request_count["n"] += 1
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "proxies": [
                                    {"ip": "8.8.8.8", "port": 8080, "protocol": "http", "confidence": 0.95}
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 1200, "completion_tokens": 200, "total_tokens": 1400},
        }
        return _DummyResponse(payload)

    monkeypatch.setattr("crawler.llm_caller.requests.post", fake_post)

    first = handler.handle_extraction_failure("<html>p1</html>", context={"reason": "failed_parse"})
    second = handler.handle_extraction_failure("<html>p2</html>", context={"reason": "failed_parse"})

    assert request_count["n"] == 1
    assert first.get("proxies")
    assert second.get("skipped") is True
    assert second.get("reason") == "cost_limit_reached"
