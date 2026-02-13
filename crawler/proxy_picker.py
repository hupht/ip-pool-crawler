from __future__ import annotations

import random
from typing import Iterable, Optional, Sequence

import requests

from crawler.config import Settings
from crawler.storage import (
    fetch_mysql_candidates as _fetch_mysql_candidates_from_db,
    fetch_proxy_countries as _fetch_proxy_countries_from_db,
    get_mysql_connection,
    get_redis_client,
)
from crawler.validator import tcp_check


DEFAULT_PROTOCOLS = ["http", "https"]


def parse_redis_key(key: str) -> Optional[dict]:
    parts = key.split(":")
    if len(parts) != 3:
        return None
    ip, port_raw, protocol = parts
    if not ip or not port_raw or not protocol:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        return None
    return {"ip": ip, "port": port, "protocol": protocol.lower()}


def allocate_protocols(protocols: Optional[Sequence[str]], count: int) -> list[str]:
    if count <= 0:
        return []
    if protocols:
        normalized = [p.lower() for p in protocols if p]
        if not normalized:
            normalized = DEFAULT_PROTOCOLS
    else:
        normalized = DEFAULT_PROTOCOLS

    result: list[str] = []
    for index in range(count):
        result.append(normalized[index % len(normalized)])
    return result


def _fetch_redis_candidates(redis_client, limit: int) -> list[dict]:
    if not redis_client or limit <= 0:
        return []
    keys = redis_client.zrevrange("proxy:alive", 0, max(0, limit - 1))
    candidates: list[dict] = []
    for key in keys:
        parsed = parse_redis_key(key)
        if parsed:
            candidates.append({**parsed, "country": None, "latency_ms": None})
    return candidates


def _fetch_mysql_candidates(
    mysql_conn,
    protocols: Sequence[str],
    countries: Optional[Sequence[str]],
    limit: int,
) -> list[dict]:
    return _fetch_mysql_candidates_from_db(mysql_conn, protocols, countries, limit)


def _filter_candidates_by_countries(mysql_conn, candidates: list[dict], countries: Sequence[str]) -> list[dict]:
    if not mysql_conn or not candidates or not countries:
        return []
    mapping = _fetch_proxy_countries_from_db(mysql_conn, candidates)
    normalized = {country.lower() for country in countries}
    filtered: list[dict] = []
    for candidate in candidates:
        key = (candidate["ip"], candidate["port"], candidate["protocol"])
        country = mapping.get(key)
        if country:
            candidate["country"] = country
            if country.lower() in normalized:
                filtered.append(candidate)
    return filtered


def _build_proxy_url(candidate: dict) -> str:
    return f"{candidate['protocol']}://{candidate['ip']}:{candidate['port']}"


def _http_check(url: str, candidate: dict, timeout: int, user_agent: str) -> bool:
    proxy_url = _build_proxy_url(candidate)
    proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }
    headers = {"User-Agent": user_agent}
    try:
        response = requests.get(url, proxies=proxies, timeout=timeout, headers=headers)
        return response.status_code < 500
    except Exception:
        return False


def _validate_candidate(candidate: dict, settings: Settings, check_url: Optional[str]) -> Optional[dict]:
    success, latency_ms = tcp_check(candidate["ip"], candidate["port"], timeout=settings.http_timeout)
    if not success:
        return None

    if check_url:
        url = check_url
    else:
        url = "https://example.com" if candidate["protocol"] == "https" else "http://example.com"

    if not _http_check(url, candidate, settings.http_timeout, settings.user_agent):
        return None

    return {
        **candidate,
        "latency_ms": latency_ms,
    }


def _pick_candidates(
    candidates: list[dict],
    protocol_allocation: Sequence[str],
    require_check: bool,
    settings: Settings,
    check_url: Optional[str],
) -> list[dict]:
    pools: dict[str, list[dict]] = {protocol: [] for protocol in set(protocol_allocation)}
    extras: list[dict] = []
    for candidate in candidates:
        protocol = candidate.get("protocol")
        if protocol in pools:
            pools[protocol].append(candidate)
        else:
            extras.append(candidate)

    selected: list[dict] = []
    for protocol in protocol_allocation:
        pool = pools.get(protocol) or []
        while pool:
            candidate = pool.pop(0)
            if not require_check:
                selected.append(candidate)
                break
            checked = _validate_candidate(candidate, settings, check_url)
            if checked:
                selected.append(checked)
                break

    if len(selected) < len(protocol_allocation):
        remaining: list[dict] = list(extras)
        for pool in pools.values():
            remaining.extend(pool)
        for candidate in remaining:
            if len(selected) >= len(protocol_allocation):
                break
            if not require_check:
                selected.append(candidate)
                continue
            checked = _validate_candidate(candidate, settings, check_url)
            if checked:
                selected.append(checked)

    return selected


def pick_proxies(
    settings: Settings,
    protocols: Optional[Sequence[str]] = None,
    countries: Optional[Sequence[str]] = None,
    count: int = 1,
    check_url: Optional[str] = None,
    require_check: bool = True,
    redis_client=None,
    mysql_conn=None,
) -> dict:
    if count <= 0:
        return {"status": "empty", "data": []}

    if protocols:
        protocol_pool = [protocol.lower() for protocol in protocols if protocol]
        if not protocol_pool:
            protocol_pool = DEFAULT_PROTOCOLS
    else:
        protocol_pool = DEFAULT_PROTOCOLS

    protocol_allocation = allocate_protocols(protocol_pool, count)
    protocol_set = set(protocol_pool)
    country_filter = [country for country in (countries or []) if country]

    status = "ok"
    messages: list[str] = []
    candidates: list[dict] = []
    mysql_conn_local = None

    try:
        if mysql_conn is None:
            mysql_conn_local = get_mysql_connection(settings)
            mysql_conn = mysql_conn_local
        if redis_client is None:
            redis_client = get_redis_client(settings)

        try:
            candidates = _fetch_redis_candidates(redis_client, max(count * 5, 20))
        except Exception:
            messages.append("redis_unavailable")
            candidates = []

        candidates = [candidate for candidate in candidates if candidate["protocol"] in protocol_set]

        if country_filter:
            filtered = _filter_candidates_by_countries(mysql_conn, candidates, country_filter)
            if filtered:
                candidates = filtered
            else:
                if candidates:
                    status = "not_found_country_fallback"
        needed = max(0, count - len(candidates))

        if needed > 0:
            try:
                if country_filter and status != "not_found_country_fallback":
                    mysql_candidates = _fetch_mysql_candidates(
                        mysql_conn,
                        list(protocol_set),
                        country_filter,
                        max(needed * 5, needed),
                    )
                    if not mysql_candidates:
                        status = "not_found_country_fallback"
                        mysql_candidates = _fetch_mysql_candidates(
                            mysql_conn,
                            list(protocol_set),
                            None,
                            max(needed * 5, needed),
                        )
                else:
                    mysql_candidates = _fetch_mysql_candidates(
                        mysql_conn,
                        list(protocol_set),
                        None,
                        max(needed * 5, needed),
                    )
                candidates.extend(mysql_candidates)
            except Exception:
                messages.append("mysql_unavailable")

        if status == "not_found_country_fallback":
            random.shuffle(candidates)

        selected = _pick_candidates(candidates, protocol_allocation, require_check, settings, check_url)

        if not selected:
            if messages:
                return {"status": "error", "message": ",".join(messages), "data": None}
            return {"status": "empty", "data": None}

        if len(selected) < count and status == "ok":
            status = "insufficient_valid"

        data = selected[0] if count == 1 else selected
        result = {"status": status, "data": data}
        if messages:
            result["message"] = ",".join(messages)
        return result
    finally:
        if mysql_conn_local is not None:
            mysql_conn_local.close()
