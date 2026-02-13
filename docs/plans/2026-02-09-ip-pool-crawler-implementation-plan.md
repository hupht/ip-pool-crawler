# IP Pool Crawler Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local Python crawler in a new folder under TestMorph that scrapes public proxy lists, validates, stores in MySQL, and maintains a Redis pool on a daily schedule.

**Architecture:** Implement a pipeline with source-specific parsers, a validator, and storage adapters for MySQL and Redis. Use a single CLI entrypoint to run one full crawl/validate cycle.

**Tech Stack:** Python 3.x, requests, beautifulsoup4, pymysql, redis, python-dotenv, pytest

---

### Task 1: Create project folder and bootstrap config

**Files:**
- Create: `ip-pool-crawler/README.md`
- Create: `ip-pool-crawler/requirements.txt`
- Create: `ip-pool-crawler/.env.example`

**Step 1: Write the failing test**

Create `ip-pool-crawler/tests/test_env.py`:

```python
from crawler.config import Settings


def test_settings_loads_defaults():
    settings = Settings.from_env()
    assert settings.http_timeout > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest ip-pool-crawler/tests/test_env.py::test_settings_loads_defaults -v`
Expected: FAIL with import error (crawler module missing)

**Step 3: Write minimal implementation**

Create `ip-pool-crawler/crawler/config.py` with minimal `Settings` class and `from_env()` loading defaults.

**Step 4: Run test to verify it passes**

Run: `pytest ip-pool-crawler/tests/test_env.py::test_settings_loads_defaults -v`
Expected: PASS

**Step 5: Commit** (skip if no git)

---

### Task 2: Define database schema and connection helpers

**Files:**
- Create: `ip-pool-crawler/sql/schema.sql`
- Create: `ip-pool-crawler/crawler/db.py`
- Test: `ip-pool-crawler/tests/test_db_sql.py`

**Step 1: Write the failing test**

```python
from pathlib import Path


def test_schema_contains_tables():
    schema = Path("ip-pool-crawler/sql/schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE proxy_sources" in schema
    assert "CREATE TABLE proxy_ips" in schema
```

**Step 2: Run test to verify it fails**

Run: `pytest ip-pool-crawler/tests/test_db_sql.py::test_schema_contains_tables -v`
Expected: FAIL (file not found)

**Step 3: Write minimal implementation**

Add `schema.sql` with tables and indexes from the design doc.

**Step 4: Run test to verify it passes**

Run: `pytest ip-pool-crawler/tests/test_db_sql.py::test_schema_contains_tables -v`
Expected: PASS

**Step 5: Commit** (skip if no git)

---

### Task 3: Implement source registry and fetcher

**Files:**
- Create: `ip-pool-crawler/crawler/sources.py`
- Create: `ip-pool-crawler/crawler/fetcher.py`
- Test: `ip-pool-crawler/tests/test_sources.py`

**Step 1: Write the failing test**

```python
from crawler.sources import get_sources


def test_sources_include_all():
    sources = get_sources()
    assert len(sources) == 5
    assert any(s.name == "free-proxy-list" for s in sources)
```

**Step 2: Run test to verify it fails**

Run: `pytest ip-pool-crawler/tests/test_sources.py::test_sources_include_all -v`
Expected: FAIL (crawler module missing or get_sources missing)

**Step 3: Write minimal implementation**

Add a `Source` dataclass and `get_sources()` returning the 5 URLs from the design.

**Step 4: Run test to verify it passes**

Run: `pytest ip-pool-crawler/tests/test_sources.py::test_sources_include_all -v`
Expected: PASS

**Step 5: Commit** (skip if no git)

---

### Task 4: Add parsers for HTML and JSON sources

**Files:**
- Create: `ip-pool-crawler/crawler/parsers.py`
- Create: `ip-pool-crawler/tests/fixtures/` (HTML/JSON samples)
- Test: `ip-pool-crawler/tests/test_parsers.py`

**Step 1: Write the failing test**

```python
from crawler.parsers import parse_free_proxy_list


def test_parse_free_proxy_list():
    html = open("ip-pool-crawler/tests/fixtures/free-proxy-list.html", "r", encoding="utf-8").read()
    records = parse_free_proxy_list(html)
    assert records
    assert records[0]["ip"]
    assert records[0]["port"]
```

**Step 2: Run test to verify it fails**

Run: `pytest ip-pool-crawler/tests/test_parsers.py::test_parse_free_proxy_list -v`
Expected: FAIL (fixture or parser missing)

**Step 3: Write minimal implementation**

Add fixture samples and implement parser functions per source.

**Step 4: Run test to verify it passes**

Run: `pytest ip-pool-crawler/tests/test_parsers.py::test_parse_free_proxy_list -v`
Expected: PASS

**Step 5: Commit** (skip if no git)

---

### Task 5: Implement validator and scoring

**Files:**
- Create: `ip-pool-crawler/crawler/validator.py`
- Test: `ip-pool-crawler/tests/test_validator.py`

**Step 1: Write the failing test**

```python
from crawler.validator import score_proxy


def test_score_proxy_prefers_lower_latency():
    s1 = score_proxy(latency_ms=100, success=True)
    s2 = score_proxy(latency_ms=500, success=True)
    assert s1 > s2
```

**Step 2: Run test to verify it fails**

Run: `pytest ip-pool-crawler/tests/test_validator.py::test_score_proxy_prefers_lower_latency -v`
Expected: FAIL (function missing)

**Step 3: Write minimal implementation**

Implement `score_proxy` and a lightweight TCP validator.

**Step 4: Run test to verify it passes**

Run: `pytest ip-pool-crawler/tests/test_validator.py::test_score_proxy_prefers_lower_latency -v`
Expected: PASS

**Step 5: Commit** (skip if no git)

---

### Task 6: Implement storage adapters (MySQL + Redis)

**Files:**
- Create: `ip-pool-crawler/crawler/storage.py`
- Test: `ip-pool-crawler/tests/test_storage.py`

**Step 1: Write the failing test**

```python
from crawler.storage import make_redis_key


def test_make_redis_key():
    key = make_redis_key("1.2.3.4", 8080, "http")
    assert key == "1.2.3.4:8080:http"
```

**Step 2: Run test to verify it fails**

Run: `pytest ip-pool-crawler/tests/test_storage.py::test_make_redis_key -v`
Expected: FAIL (function missing)

**Step 3: Write minimal implementation**

Add Redis helper and MySQL upsert helpers. Keep I/O behind small functions for testing.

**Step 4: Run test to verify it passes**

Run: `pytest ip-pool-crawler/tests/test_storage.py::test_make_redis_key -v`
Expected: PASS

**Step 5: Commit** (skip if no git)

---

### Task 7: Build pipeline runner and CLI

**Files:**
- Create: `ip-pool-crawler/main.py`
- Create: `ip-pool-crawler/crawler/pipeline.py`
- Test: `ip-pool-crawler/tests/test_pipeline_smoke.py`

**Step 1: Write the failing test**

```python
from crawler.pipeline import normalize_record


def test_normalize_record_min_fields():
    record = normalize_record({"ip": "1.1.1.1", "port": "80"})
    assert record["ip"] == "1.1.1.1"
    assert record["port"] == 80
```

**Step 2: Run test to verify it fails**

Run: `pytest ip-pool-crawler/tests/test_pipeline_smoke.py::test_normalize_record_min_fields -v`
Expected: FAIL (function missing)

**Step 3: Write minimal implementation**

Implement normalization and main entrypoint `python main.py --once`.

**Step 4: Run test to verify it passes**

Run: `pytest ip-pool-crawler/tests/test_pipeline_smoke.py::test_normalize_record_min_fields -v`
Expected: PASS

**Step 5: Commit** (skip if no git)

---

### Task 8: Document run and scheduling instructions

**Files:**
- Modify: `ip-pool-crawler/README.md`

**Step 1: Write the failing test**

Create `ip-pool-crawler/tests/test_readme.py`:

```python
from pathlib import Path


def test_readme_mentions_scheduler():
    text = Path("ip-pool-crawler/README.md").read_text(encoding="utf-8")
    assert "Task Scheduler" in text
    assert "cron" in text
```

**Step 2: Run test to verify it fails**

Run: `pytest ip-pool-crawler/tests/test_readme.py::test_readme_mentions_scheduler -v`
Expected: FAIL (README not updated)

**Step 3: Write minimal implementation**

Add setup, schema, and scheduling instructions to README.

**Step 4: Run test to verify it passes**

Run: `pytest ip-pool-crawler/tests/test_readme.py::test_readme_mentions_scheduler -v`
Expected: PASS

**Step 5: Commit** (skip if no git)

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-02-09-ip-pool-crawler-implementation-plan.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
