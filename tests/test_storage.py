from crawler.storage import make_redis_key


def test_make_redis_key():
    key = make_redis_key("1.2.3.4", 8080, "http")
    assert key == "1.2.3.4:8080:http"


def test_upsert_redis_pool_swallows_errors():
    class DummyRedis:
        def zadd(self, *_args, **_kwargs):
            raise Exception("boom")

    from crawler.storage import upsert_redis_pool

    upsert_redis_pool(DummyRedis(), "1.2.3.4", 8080, "http", 1)


def test_upsert_proxy_restores_deleted_flag():
    captured = {}

    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def execute(self, query, _params):
            captured["query"] = query

    class DummyConn:
        def cursor(self):
            return DummyCursor()

    from crawler.storage import upsert_proxy

    upsert_proxy(DummyConn(), "1.2.3.4", 8080, "http", None, None, None)

    query = captured["query"]
    assert "ON DUPLICATE KEY UPDATE" in query
    assert "is_deleted=0" in query
    assert "fail_window_start=NULL" in query
    assert "fail_count=0" in query


def test_run_with_schema_retry_executes_schema_on_missing_table():
    import pymysql

    executed = []

    class DummyCursor:
        def __init__(self, conn):
            self._conn = conn

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def execute(self, query, _params=None):
            executed.append(query)
            if self._conn.calls == 0:
                self._conn.calls += 1
                raise pymysql.err.ProgrammingError(1146, "Table 'proxy_ips' doesn't exist")
            self._conn.calls += 1

    class DummyConn:
        def __init__(self):
            self.calls = 0

        def cursor(self, *_args, **_kwargs):
            return DummyCursor(self)

        def ping(self, *_args, **_kwargs):
            pass

    from crawler.storage import _run_with_schema_retry
    from unittest.mock import MagicMock, patch

    def runner(cursor):
        cursor.execute("SELECT * FROM proxy_ips")
        return "ok"

    settings = MagicMock()
    settings.mysql_host = "localhost"
    settings.mysql_port = 3306
    settings.mysql_user = "root"
    settings.mysql_password = ""
    settings.mysql_database = "test_db"

    with patch("crawler.storage._init_database_and_schema"):
        result = _run_with_schema_retry(DummyConn(), settings, runner)

    assert result == "ok"


def test_insert_crawl_session_returns_id():
    class DummyCursor:
        lastrowid = 101

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def execute(self, _query, _params=None):
            return None

    class DummyConn:
        def cursor(self):
            return DummyCursor()

    from crawler.storage import insert_crawl_session

    result = insert_crawl_session(DummyConn(), {"user_url": "https://example.com"})
    assert result == 101


def test_insert_page_log_returns_id():
    class DummyCursor:
        lastrowid = 202

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def execute(self, _query, _params=None):
            return None

    class DummyConn:
        def cursor(self):
            return DummyCursor()

    from crawler.storage import insert_page_log

    result = insert_page_log(DummyConn(), {"session_id": 1, "page_url": "https://example.com"})
    assert result == 202


def test_insert_review_queue_item_returns_id():
    class DummyCursor:
        lastrowid = 303

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def execute(self, _query, _params=None):
            return None

    class DummyConn:
        def cursor(self):
            return DummyCursor()

    from crawler.storage import insert_review_queue_item

    result = insert_review_queue_item(
        DummyConn(),
        {"session_id": 1, "page_log_id": 1, "ip": "1.2.3.4", "port": 8080},
    )
    assert result == 303


def test_insert_llm_call_log_returns_id():
    class DummyCursor:
        lastrowid = 404

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def execute(self, _query, _params=None):
            return None

    class DummyConn:
        def cursor(self):
            return DummyCursor()

    from crawler.storage import insert_llm_call_log

    result = insert_llm_call_log(
        DummyConn(),
        {"session_id": 1, "llm_model": "gpt-4o-mini", "llm_base_url": "https://api.openai.com/v1"},
    )
    assert result == 404


def test_check_duplicate_with_session():
    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def execute(self, _query, _params=None):
            return None

        def fetchone(self):
            return (1,)

    class DummyConn:
        def cursor(self):
            return DummyCursor()

    from crawler.storage import check_duplicate

    assert check_duplicate(DummyConn(), "1.2.3.4", 8080, "http", session_id=10) is True


def test_check_duplicate_without_session():
    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def execute(self, _query, _params=None):
            return None

        def fetchone(self):
            return (0,)

    class DummyConn:
        def cursor(self):
            return DummyCursor()

    from crawler.storage import check_duplicate

    assert check_duplicate(DummyConn(), "1.2.3.4", 8080, "http") is False


def test_fetch_proxy_countries_uses_ip_port_protocol_key():
    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def execute(self, _query, _params=None):
            return None

        def fetchall(self):
            return [("1.2.3.4", 8080, "http", "US")]

    class DummyConn:
        def cursor(self):
            return DummyCursor()

    from crawler.storage import fetch_proxy_countries

    mapping = fetch_proxy_countries(
        DummyConn(),
        [{"ip": "1.2.3.4", "port": 8080, "protocol": "http"}],
    )

    assert mapping[("1.2.3.4", 8080, "http")] == "US"
