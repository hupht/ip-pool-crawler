from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from crawler.llm_cache import LLMCache
from crawler.llm_caller import LLMCaller
from crawler.llm_config import LLMConfig
from crawler.proxy_validator import ProxyValidator
from crawler.universal_parser import UniversalParser
from crawler.validator import Validator


@dataclass
class ErrorHandlerConfig:
    low_confidence_threshold: float = 0.5


class ErrorHandler:
    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        llm_caller: Optional[LLMCaller] = None,
        llm_cache: Optional[LLMCache] = None,
        config: Optional[ErrorHandlerConfig] = None,
    ):
        self.llm_config = llm_config or LLMConfig.from_env()
        self.llm_caller = llm_caller or LLMCaller(self.llm_config)
        self.llm_cache = llm_cache or LLMCache(default_ttl_hours=self.llm_config.cache_ttl_hours)
        self.config = config or ErrorHandlerConfig()
        self.validator = Validator(suspicious_threshold=self.config.low_confidence_threshold)
        self._accumulated_cost_usd = 0.0

    @property
    def accumulated_cost_usd(self) -> float:
        return float(self._accumulated_cost_usd)

    def _can_afford_ai_call(self) -> bool:
        return self._accumulated_cost_usd < float(self.llm_config.cost_limit_usd)

    def should_use_ai(self, reason: str) -> bool:
        if not self.llm_config.enabled:
            return False
        reason_map = {
            "low_confidence": self.llm_config.trigger_on_low_confidence,
            "no_table": self.llm_config.trigger_on_no_table,
            "failed_parse": self.llm_config.trigger_on_failed_parse,
            "user_request": self.llm_config.trigger_on_user_request,
        }
        return bool(reason_map.get(reason, False))

    def handle_extraction_failure(self, html: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        if not self._can_afford_ai_call():
            return {
                "proxies": [],
                "skipped": True,
                "reason": "cost_limit_reached",
                "cost_limit_usd": float(self.llm_config.cost_limit_usd),
                "accumulated_cost_usd": float(self._accumulated_cost_usd),
            }

        if self.llm_config.cache_enabled:
            cache_key = LLMCache.build_cache_key(html, context)
            cached = self.llm_cache.get(cache_key)
            if cached is not None:
                cached_result = dict(cached)
                cached_result["cache_hit"] = True
                cached_result["accumulated_cost_usd"] = float(self._accumulated_cost_usd)
                return cached_result
        else:
            cache_key = None

        result = self.llm_caller.call_llm_for_parsing(html=html, context=context)
        call_cost = float(result.get("cost_usd", 0.0) or 0.0)
        self._accumulated_cost_usd += max(0.0, call_cost)
        result["accumulated_cost_usd"] = float(self._accumulated_cost_usd)
        if self.llm_config.cache_enabled and cache_key is not None and "error" not in result:
            self.llm_cache.set(cache_key, result)
        return result

    def process_page(
        self,
        html: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        valid_data, review_data, _meta = self.process_page_with_meta(html=html, context=context)
        return valid_data, review_data

    def process_page_with_meta(
        self,
        html: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        context = context or {}
        extracted, stats = UniversalParser.extract_all(html)

        valid_data: List[Dict[str, Any]] = []
        review_data: List[Dict[str, Any]] = []
        meta: Dict[str, Any] = {
            "ai_called": False,
            "ai_reason": None,
            "ai_result": None,
            "stats": stats,
        }

        for item in UniversalParser.deduplicate_proxies(extracted):
            candidate = {
                "ip": item.ip,
                "port": item.port,
                "protocol": item.protocol or "http",
                "confidence": item.confidence,
                "source": item.source_type,
            }

            suspicious = self.validator.mark_suspicious_data(candidate)
            if suspicious.get("is_suspicious"):
                reasons = suspicious.get("suspicious_reasons") or []
                candidate["review_reason"] = ",".join(reasons) if reasons else "validation_failed"
                candidate["validation_confidence"] = 0.0
                review_data.append(candidate)
                continue

            validation = ProxyValidator.validate_proxy(candidate["ip"], candidate["port"], candidate["protocol"])
            if validation.is_valid and candidate["confidence"] >= self.config.low_confidence_threshold:
                valid_data.append(candidate)
            else:
                candidate["review_reason"] = (
                    "low_confidence"
                    if validation.is_valid and candidate["confidence"] < self.config.low_confidence_threshold
                    else "validation_failed"
                )
                candidate["validation_confidence"] = validation.confidence
                review_data.append(candidate)

        reason = ""
        if not extracted:
            reason = "failed_parse"
        elif stats.get("from_tables", 0) == 0:
            reason = "no_table"
        elif valid_data:
            avg_conf = sum(item["confidence"] for item in valid_data) / len(valid_data)
            if avg_conf < self.config.low_confidence_threshold:
                reason = "low_confidence"

        if reason and self.should_use_ai(reason):
            ai_result = self.handle_extraction_failure(html=html, context={**context, "reason": reason})
            meta["ai_called"] = True
            meta["ai_reason"] = reason
            meta["ai_result"] = ai_result
            for proxy in ai_result.get("proxies", []):
                candidate = {
                    "ip": proxy.get("ip"),
                    "port": proxy.get("port"),
                    "protocol": proxy.get("protocol") or "http",
                    "confidence": float(proxy.get("confidence", 0.9)),
                    "source": "ai",
                }
                validation = ProxyValidator.validate_proxy(candidate["ip"], candidate["port"], candidate["protocol"])
                if validation.is_valid:
                    valid_data.append(candidate)
                else:
                    candidate["review_reason"] = "ai_validation_failed"
                    candidate["validation_confidence"] = validation.confidence
                    review_data.append(candidate)

        return valid_data, review_data, meta
