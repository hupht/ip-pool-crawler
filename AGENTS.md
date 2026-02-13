# AGENTS Guide (for other agents)

## Purpose
Keep changes aligned with the current crawler design and avoid regressions. This repo is a Python-based IP pool crawler with MySQL + Redis.

## Entry Points
- Main crawler: [main.py](main.py)
- Unified CLI: [cli.py](cli.py)

## Key Modules
- Sources: [crawler/sources.py](crawler/sources.py)
- Fetching: [crawler/fetcher.py](crawler/fetcher.py)
- Parsing: [crawler/parsers.py](crawler/parsers.py)
- Pipeline: [crawler/pipeline.py](crawler/pipeline.py)
- Validation: [crawler/validator.py](crawler/validator.py)
- Storage: [crawler/storage.py](crawler/storage.py)
- Runtime env loader: [crawler/runtime.py](crawler/runtime.py)

## Architecture Flow
sources → fetch → parse → normalize → upsert → TCP check → score → MySQL/Redis updates

## Environment
- `.env` is required; template in [.env.example](.env.example)
- Important settings: `MYSQL_*`, `REDIS_*`, `HTTP_TIMEOUT`, `SOURCE_WORKERS`, `VALIDATE_WORKERS`

## Commands
- Run crawler: `python main.py` or `python cli.py run`
- Run checker: `python cli.py check`
- Get proxies: `python cli.py get-proxy --protocol http,https --country US --count 3`
- Diagnostics: `python cli.py diagnose-sources | diagnose-pipeline | diagnose-html | redis-ping`

## Concurrency Defaults (2C/2G)
- `SOURCE_WORKERS=2`
- `VALIDATE_WORKERS=30`

## Tests
- All tests: `python -m pytest tests`
- Common targeted tests: `python -m pytest tests/test_env.py`

## Conventions
- Prefer small functions and dataclasses
- Core pipeline modules avoid printing; tools can print
- Soft delete uses `is_deleted=1`

## Notes
- Source data is API-based; no browser dependency expected.
- Keep schema in [sql/schema.sql](sql/schema.sql) consistent with storage logic.
