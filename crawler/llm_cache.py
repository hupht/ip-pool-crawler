from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
import hashlib
import json
from threading import Lock
from typing import Any, Dict, Optional


@dataclass
class CacheItem:
    value: Dict[str, Any]
    expires_at: datetime


class LLMCache:
    def __init__(self, default_ttl_hours: int = 24):
        self.default_ttl_hours = max(1, int(default_ttl_hours))
        self._store: Dict[str, CacheItem] = {}
        self._lock = Lock()

    @staticmethod
    def build_cache_key(html: str, context: Optional[Dict[str, Any]] = None) -> str:
        context = context or {}
        payload = {
            "html": html,
            "context": context,
        }
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        now = datetime.now(UTC)
        with self._lock:
            item = self._store.get(cache_key)
            if item is None:
                return None
            if item.expires_at <= now:
                del self._store[cache_key]
                return None
            return item.value

    def set(self, cache_key: str, result: Dict[str, Any], ttl_hours: Optional[int] = None) -> None:
        ttl = self.default_ttl_hours if ttl_hours is None else max(1, int(ttl_hours))
        expires_at = datetime.now(UTC) + timedelta(hours=ttl)
        with self._lock:
            self._store[cache_key] = CacheItem(value=result, expires_at=expires_at)

    def clear_expired(self) -> int:
        now = datetime.now(UTC)
        removed = 0
        with self._lock:
            expired_keys = [key for key, item in self._store.items() if item.expires_at <= now]
            for key in expired_keys:
                del self._store[key]
                removed += 1
        return removed

    def size(self) -> int:
        with self._lock:
            return len(self._store)
