from crawler.error_handler import ErrorHandler, ErrorHandlerConfig
from crawler.llm_config import LLMConfig


def test_should_use_ai_by_trigger_flags():
    cfg = LLMConfig(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        enabled=True,
        trigger_on_low_confidence=True,
        trigger_on_no_table=False,
        trigger_on_failed_parse=True,
        trigger_on_user_request=True,
    )
    handler = ErrorHandler(llm_config=cfg)

    assert handler.should_use_ai("low_confidence") is True
    assert handler.should_use_ai("no_table") is False
    assert handler.should_use_ai("failed_parse") is True


def test_process_page_heuristic_success_without_ai(monkeypatch):
    cfg = LLMConfig(base_url="https://api.openai.com/v1", model="gpt-4o-mini", api_key="sk-test", enabled=False)
    handler = ErrorHandler(llm_config=cfg, config=ErrorHandlerConfig(low_confidence_threshold=0.5))

    html = "<html><body>1.2.3.4:8080:http</body></html>"
    valid, review = handler.process_page(html, context={})

    assert len(valid) >= 1
    assert len(review) >= 0


def test_process_page_fallback_to_ai_on_failed_parse(monkeypatch):
    cfg = LLMConfig(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        enabled=True,
        trigger_on_failed_parse=True,
    )
    handler = ErrorHandler(llm_config=cfg)

    monkeypatch.setattr(
        "crawler.error_handler.UniversalParser.extract_all",
        lambda html: ([], {"from_tables": 0, "total_extracted": 0}),
    )

    monkeypatch.setattr(
        handler.llm_caller,
        "call_llm_for_parsing",
        lambda html, context: {"proxies": [{"ip": "1.2.3.4", "port": 8080, "protocol": "http", "confidence": 0.9}]},
    )

    valid, review = handler.process_page("<html></html>", context={})

    assert len(valid) == 1
    assert valid[0]["source"] == "ai"
    assert len(review) == 0


def test_handle_extraction_failure_uses_cache(monkeypatch):
    cfg = LLMConfig(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        enabled=True,
        cache_enabled=True,
    )
    handler = ErrorHandler(llm_config=cfg)

    call_count = {"n": 0}

    def fake_call(html, context):
        call_count["n"] += 1
        return {"proxies": [{"ip": "1.2.3.4", "port": 8080}]}

    monkeypatch.setattr(handler.llm_caller, "call_llm_for_parsing", fake_call)

    html = "<html>sample</html>"
    context = {"reason": "failed_parse"}

    first = handler.handle_extraction_failure(html, context)
    second = handler.handle_extraction_failure(html, context)

    assert call_count["n"] == 1
    assert "proxies" in first
    assert second.get("cache_hit") is True


def test_handle_extraction_failure_respects_cost_limit(monkeypatch):
    cfg = LLMConfig(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        enabled=True,
        cache_enabled=False,
        cost_limit_usd=0.001,
    )
    handler = ErrorHandler(llm_config=cfg)

    call_count = {"n": 0}

    def fake_call(html, context):
        call_count["n"] += 1
        return {
            "proxies": [{"ip": "1.2.3.4", "port": 8080, "protocol": "http", "confidence": 0.9}],
            "cost_usd": 0.002,
        }

    monkeypatch.setattr(handler.llm_caller, "call_llm_for_parsing", fake_call)

    first = handler.handle_extraction_failure("<html>a</html>", {"reason": "failed_parse"})
    second = handler.handle_extraction_failure("<html>b</html>", {"reason": "failed_parse"})

    assert call_count["n"] == 1
    assert first.get("proxies")
    assert second.get("skipped") is True
    assert second.get("reason") == "cost_limit_reached"


def test_process_page_uses_validator_layer(monkeypatch):
    cfg = LLMConfig(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        enabled=False,
    )
    handler = ErrorHandler(llm_config=cfg)

    call_count = {"n": 0}

    def fake_mark(record):
        call_count["n"] += 1
        return {
            **record,
            "is_suspicious": True,
            "suspicious_reasons": ["low_confidence"],
        }

    monkeypatch.setattr(handler.validator, "mark_suspicious_data", fake_mark)

    valid, review = handler.process_page("<html><body>1.2.3.4:8080:http</body></html>", context={})

    assert call_count["n"] >= 1
    assert len(valid) == 0
    assert len(review) >= 1
    assert "review_reason" in review[0]
