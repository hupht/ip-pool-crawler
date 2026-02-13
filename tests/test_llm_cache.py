from datetime import datetime, timedelta, UTC

from crawler.llm_cache import CacheItem, LLMCache


def test_build_cache_key_stable():
    html = "<html>1.2.3.4:8080</html>"
    context = {"source": "unit-test", "hint": "table"}

    key1 = LLMCache.build_cache_key(html, context)
    key2 = LLMCache.build_cache_key(html, context)

    assert key1 == key2
    assert len(key1) == 64


def test_set_and_get_cache_value():
    cache = LLMCache(default_ttl_hours=24)
    key = LLMCache.build_cache_key("<html>...</html>", {"a": 1})

    payload = {"proxies": [{"ip": "1.2.3.4", "port": 8080}]}
    cache.set(key, payload)

    value = cache.get(key)
    assert value == payload


def test_get_expired_returns_none():
    cache = LLMCache(default_ttl_hours=24)
    key = "expired-key"
    cache.set(key, {"proxies": []})

    cache._store[key] = CacheItem(value={"proxies": []}, expires_at=datetime.now(UTC) - timedelta(seconds=1))

    assert cache.get(key) is None


def test_clear_expired_removes_items():
    cache = LLMCache(default_ttl_hours=24)

    cache.set("active", {"ok": True})
    cache.set("expired", {"ok": False})
    cache._store["expired"] = CacheItem(value={"ok": False}, expires_at=datetime.now(UTC) - timedelta(seconds=1))

    removed = cache.clear_expired()

    assert removed == 1
    assert cache.get("expired") is None
    assert cache.get("active") == {"ok": True}


def test_size_tracks_entries():
    cache = LLMCache(default_ttl_hours=24)

    cache.set("k1", {"v": 1})
    cache.set("k2", {"v": 2})

    assert cache.size() == 2
