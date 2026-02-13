# IP Pool Crawler Design (MySQL + Redis)

Date: 2026-02-09

## Goal
Build a scheduled crawler that collects public proxy IPs, validates them, stores history in MySQL, and serves a fast pool from Redis. Runs daily at 03:00 local time on Windows Task Scheduler or Linux cron.

## Scope
- Scrape from the following sources (public lists only):
  - https://www.free-proxy-list.net/
  - https://www.sslproxies.org/
  - https://www.us-proxy.org/
  - https://www.proxy-list.download/
  - https://www.geonode.com/free-proxy-list/
- Parse and normalize IP records.
- Optional validation (TCP first, HTTP later).
- Persist history in MySQL.
- Maintain a fast, scored pool in Redis.

## Architecture
Pipeline stages:
1) Scraper: fetch raw HTML/JSON with timeouts, retries, and polite headers.
2) Parser: extract ip/port/protocol/anonymity/country into a normalized record.
3) Validator: check reachability (TCP) and update status/latency.
4) Store/Pool: write to MySQL and update Redis pool.

## Data Model (MySQL)
### Table: proxy_sources
- id (PK)
- name
- url
- parser_key
- enabled
- last_fetch_at
- fail_count
- created_at
- updated_at

### Table: proxy_ips
- id (PK)
- ip
- port
- protocol
- anonymity
- country
- region
- isp
- source_id (FK -> proxy_sources.id)
- first_seen_at
- last_seen_at
- last_checked_at
- latency_ms
- is_alive
- fail_count

Indexing:
- UNIQUE (ip, port, protocol)
- INDEX (is_alive, last_checked_at)

## Redis Pool
- ZSET proxy:alive
  - member: ip:port:protocol
  - score: computed from latency and recent success
- SET proxy:raw (optional) for pre-validation staging

Scoring idea:
- Lower latency and more recent checks yield higher score.

## Deduplication
Use UNIQUE (ip, port, protocol). On conflict, update last_seen_at and source metadata. Do not hard-delete; mark is_alive=false and keep history.

## Validation Strategy
- Phase 1: TCP connect with timeout.
- Phase 2 (optional): HTTP check against a stable endpoint.
- Update latency_ms, is_alive, last_checked_at, fail_count.

## Error Handling
- Network timeouts: retry once or twice, then mark source fail_count +1.
- Parser errors: log and skip record; track per-source errors.
- Redis failures: degrade to MySQL-only writes.

## Scheduling
- Windows Task Scheduler: daily at 03:00, run python main.py.
- Linux cron: 0 3 * * * /usr/bin/python3 /path/main.py

## Observability
- Structured logs (JSON) with counts:
  - fetched, parsed, validated, alive, inserted, updated
  - per-source duration and failure reasons

## Testing
- Unit tests for each parser with saved HTML/JSON fixtures.
- Integration test for full pipeline with mocked responses.
- Smoke test on a single source.

## Compliance
- Respect robots.txt and site TOS where applicable.
- Use reasonable timeouts and low concurrency.
- Avoid aggressive scraping.
