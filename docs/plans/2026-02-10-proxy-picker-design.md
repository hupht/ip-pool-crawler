# Proxy Picker Design

## Context
We need a Python function that selects proxies from the existing pool, optionally filtered by protocol and country, validates usability, and returns a structured result. The function will be used by future HTTP APIs but is implemented as a module-level function now.

## Goals
- Provide a function interface that returns one or many proxies.
- Default to returning one proxy when `count` is not provided.
- When `protocols` and `countries` are not provided, distribute selections across `http` and `https` and try to cover different countries.
- Prefer Redis as the primary source, then fall back to MySQL when needed.
- Validate candidates before returning (TCP then HTTP/HTTPS).
- Return structured dictionaries (not raw strings) and include a status value.

## Non-goals
- Implement a web API endpoint now.
- Provide SOCKS support or advanced health-check scoring.
- Update Redis scores or DB state as part of selection.

## Proposed API
`pick_proxies(settings, protocols=None, countries=None, count=1, check_url=None, require_check=True)`

- `protocols`: list of strings ("http", "https"); if omitted, distribute evenly.
- `countries`: list of strings; if omitted, try to cover variety where available.
- `count`: number of proxies to return (default 1).
- `check_url`: URL used for HTTP/HTTPS validation; if omitted, use defaults.
- `require_check`: when True, enforce validation checks.

Return shape:
- For `count=1`: a dict with `status` and `data` (single proxy dict) or `data=None`.
- For `count>1`: a dict with `status` and `data` (list of proxy dicts).

Proxy dict fields: `ip`, `port`, `protocol`, `country`, `latency_ms`.

## Data Flow
1. Parse inputs and build target protocol allocation.
2. Read candidate keys from Redis `proxy:alive` sorted set.
3. Convert keys to candidate tuples.
4. If country filtering is requested, batch-query MySQL to attach `country` and filter.
5. If not enough candidates, fall back to MySQL and continue selecting.
6. Validate candidates (TCP check then HTTP/HTTPS request).
7. Return the first `count` valid results. If country match fails, return fallback status and fill with random candidates.

## Redis and MySQL Access
- Redis keys: `ip:port:protocol` in `proxy:alive`.
- MySQL table: `proxy_ips` with `country`, `is_alive`, `is_deleted`, `latency_ms`, `last_checked_at`.
- Country filtering requires MySQL to map `(ip, port, protocol)` to `country`.

## Fallback Rules
- If country filter finds no matches, return status `not_found_country_fallback` and fill from remaining candidates.
- If Redis is empty or insufficient, pull additional candidates from MySQL.
- If validation eliminates too many candidates, return status `insufficient_valid` with partial data.

## Error Handling
- Redis/MySQL errors should not raise to callers; return `status="error"` with a message.
- Return `status="empty"` when no data can be provided.

## Testing Plan
- Default selection with no filters, `count=1` and `count>1`.
- Country filtering with fallback behavior.
- Redis insufficient fall back to MySQL.
- Validation logic with mocked checks.
