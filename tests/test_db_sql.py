from pathlib import Path


def test_schema_contains_tables():
    schema = Path("ip-pool-crawler/sql/schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS proxy_sources" in schema
    assert "CREATE TABLE IF NOT EXISTS proxy_ips" in schema
    assert "is_deleted" in schema
    assert "fail_window_start" in schema
