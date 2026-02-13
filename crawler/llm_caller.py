import json
from typing import Any, Dict, Optional

import requests

from crawler.llm_config import LLMConfig


MODEL_PRICING_PER_1K_TOKENS = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}


class LLMCaller:
    def __init__(self, config: LLMConfig):
        self.config = config

    def _get_html_snippet(self, html: str) -> str:
        if self.config.submit_full_html:
            return html
        max_chars = max(1, int(self.config.html_snippet_chars))
        return html[:max_chars]

    def _build_prompt(self, html: str, context: Optional[Dict[str, Any]] = None) -> str:
        context = context or {}
        html_snippet = self._get_html_snippet(html)
        context_json = json.dumps(context, ensure_ascii=False)
        template = self.config.user_prompt_template
        return (
            template
            .replace("{context_json}", context_json)
            .replace("{html_snippet}", html_snippet)
            .replace("{html}", html)
        )

    @staticmethod
    def parse_llm_response(response: str) -> Dict[str, Any]:
        text = (response or "").strip()
        if not text:
            return {"proxies": []}

        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                if "proxies" not in data or not isinstance(data.get("proxies"), list):
                    data["proxies"] = []
                return data
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                if isinstance(data, dict):
                    if "proxies" not in data or not isinstance(data.get("proxies"), list):
                        data["proxies"] = []
                    return data
            except json.JSONDecodeError:
                pass

        return {"proxies": []}

    def estimate_cost(self, input_tokens: int, output_tokens: int = 0) -> float:
        pricing = MODEL_PRICING_PER_1K_TOKENS.get(
            self.config.model,
            MODEL_PRICING_PER_1K_TOKENS["gpt-4o-mini"],
        )
        return (input_tokens / 1000.0) * pricing["input"] + (output_tokens / 1000.0) * pricing["output"]

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def call_llm_for_parsing(self, html: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.config.enabled:
            return {"proxies": [], "skipped": True, "reason": "llm disabled"}

        prompt = self._build_prompt(html, context)
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }

        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        last_error: Optional[str] = None
        for _ in range(max(1, self.config.max_retries)):
            try:
                response = requests.post(
                    endpoint,
                    headers=self._build_headers(),
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()

                choice = ((body.get("choices") or [{}])[0]).get("message", {})
                content = choice.get("content", "")
                parsed = self.parse_llm_response(content)

                usage = body.get("usage") or {}
                input_tokens = int(usage.get("prompt_tokens", 0))
                output_tokens = int(usage.get("completion_tokens", 0))
                parsed["tokens"] = {
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": int(usage.get("total_tokens", input_tokens + output_tokens)),
                }
                parsed["cost_usd"] = self.estimate_cost(input_tokens=input_tokens, output_tokens=output_tokens)
                return parsed
            except Exception as exc:
                last_error = str(exc)

        return {"proxies": [], "error": last_error or "llm call failed"}


def estimate_batch_cost(urls_count: int, ai_call_rate: float, model: str = "gpt-4o-mini") -> float:
    call_count = max(0.0, float(urls_count)) * max(0.0, min(1.0, float(ai_call_rate)))
    pricing = MODEL_PRICING_PER_1K_TOKENS.get(model, MODEL_PRICING_PER_1K_TOKENS["gpt-4o-mini"])
    avg_input_tokens = 12000
    avg_output_tokens = 1000
    per_call = (avg_input_tokens / 1000.0) * pricing["input"] + (avg_output_tokens / 1000.0) * pricing["output"]
    return call_count * per_call
