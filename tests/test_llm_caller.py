import json

from crawler.llm_caller import LLMCaller, estimate_batch_cost
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


def test_parse_llm_response_plain_json():
    text = '{"proxies":[{"ip":"1.2.3.4","port":8080,"protocol":"http"}]}'
    data = LLMCaller.parse_llm_response(text)

    assert len(data["proxies"]) == 1
    assert data["proxies"][0]["ip"] == "1.2.3.4"


def test_parse_llm_response_code_fence_json():
    text = "```json\n{\"proxies\":[{\"ip\":\"1.2.3.4\",\"port\":8080}]}\n```"
    data = LLMCaller.parse_llm_response(text)

    assert len(data["proxies"]) == 1


def test_estimate_batch_cost_positive():
    cost = estimate_batch_cost(urls_count=100, ai_call_rate=0.1, model="gpt-4o-mini")
    assert cost > 0


def test_call_llm_for_parsing_disabled():
    cfg = LLMConfig(base_url="https://api.openai.com/v1", model="gpt-4o-mini", api_key="sk-test", enabled=False)
    caller = LLMCaller(cfg)

    result = caller.call_llm_for_parsing("<html>1.2.3.4:8080</html>", context={})
    assert result["skipped"] is True


def test_call_llm_for_parsing_success(monkeypatch):
    cfg = LLMConfig(base_url="https://api.openai.com/v1", model="gpt-4o-mini", api_key="sk-test", enabled=True)
    caller = LLMCaller(cfg)

    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "proxies": [{"ip": "1.2.3.4", "port": 8080, "protocol": "http", "confidence": 0.9}]
                    })
                }
            }
        ],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 200, "total_tokens": 1400},
    }

    monkeypatch.setattr(
        "crawler.llm_caller.requests.post",
        lambda *args, **kwargs: _DummyResponse(payload),
    )

    result = caller.call_llm_for_parsing("<html>1.2.3.4:8080</html>", context={})
    assert len(result["proxies"]) == 1
    assert result["tokens"]["total"] == 1400
    assert result["cost_usd"] > 0


def test_call_llm_for_parsing_error(monkeypatch):
    cfg = LLMConfig(base_url="https://api.openai.com/v1", model="gpt-4o-mini", api_key="sk-test", enabled=True)
    caller = LLMCaller(cfg)

    def _raise(*args, **kwargs):
        raise Exception("network error")

    monkeypatch.setattr("crawler.llm_caller.requests.post", _raise)

    result = caller.call_llm_for_parsing("<html></html>", context={})
    assert "error" in result


def test_call_llm_uses_custom_prompts_and_partial_html(monkeypatch):
    cfg = LLMConfig(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        enabled=True,
        system_prompt="custom-system",
        user_prompt_template="CTX={context_json}\\nHTML={html_snippet}",
        submit_full_html=False,
        html_snippet_chars=10,
    )
    caller = LLMCaller(cfg)

    captured = {}

    def _fake_post(*args, **kwargs):
        captured["payload"] = kwargs.get("json")
        return _DummyResponse(
            {
                "choices": [{"message": {"content": json.dumps({"proxies": []})}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )

    monkeypatch.setattr("crawler.llm_caller.requests.post", _fake_post)

    caller.call_llm_for_parsing("ABCDEFGHIJKL", context={"page": 1})

    messages = captured["payload"]["messages"]
    assert messages[0]["content"] == "custom-system"
    assert "ABCDEFGHIJ" in messages[1]["content"]
    assert "ABCDEFGHIJKL" not in messages[1]["content"]


def test_call_llm_uses_full_html_when_enabled(monkeypatch):
    cfg = LLMConfig(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        enabled=True,
        submit_full_html=True,
        html_snippet_chars=5,
    )
    caller = LLMCaller(cfg)

    captured = {}

    def _fake_post(*args, **kwargs):
        captured["payload"] = kwargs.get("json")
        return _DummyResponse(
            {
                "choices": [{"message": {"content": json.dumps({"proxies": []})}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )

    monkeypatch.setattr("crawler.llm_caller.requests.post", _fake_post)

    caller.call_llm_for_parsing("ABCDEFGHIJKL", context={"page": 1})

    user_prompt = captured["payload"]["messages"][1]["content"]
    assert "ABCDEFGHIJKL" in user_prompt
