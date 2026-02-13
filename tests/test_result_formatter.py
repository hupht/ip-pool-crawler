import importlib.util
from pathlib import Path

from crawler.dynamic_crawler import DynamicCrawlResult


def _load_module():
    file_path = Path(__file__).resolve().parent.parent / "cli" / "result_formatter.py"
    spec = importlib.util.spec_from_file_location("result_formatter", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_format_crawl_result_text():
    formatter = _load_module()
    result = DynamicCrawlResult(
        url="https://example.com/proxy",
        pages_crawled=2,
        extracted=12,
        valid=10,
        invalid=2,
        stored=10,
        session_id=99,
    )

    text = formatter.format_crawl_result(result)

    assert "crawl-custom 结果" in text
    assert "pages_crawled" in text and "| 2" in text
    assert "session_id" in text and "| 99" in text
    assert "+" in text


def test_result_to_json_and_csv_rows():
    formatter = _load_module()
    result = DynamicCrawlResult(
        url="https://example.com/proxy",
        pages_crawled=1,
        extracted=5,
        valid=4,
        invalid=1,
        stored=4,
        session_id=None,
    )

    payload = formatter.result_to_json(result)
    rows = formatter.results_to_csv_rows([result])

    assert '"url": "https://example.com/proxy"' in payload
    assert rows[0]["valid"] == 4
    assert rows[0]["session_id"] is None


def test_format_extended_stats_from_dict():
    formatter = _load_module()
    result = {
        "url": "https://example.com/proxy",
        "pages_crawled": 3,
        "total_ips": 125,
        "extracted": 130,
        "valid": 120,
        "invalid": 10,
        "stored": 120,
        "avg_confidence": 0.87,
        "ai_calls_count": 2,
        "llm_cost_usd": 0.0235,
        "review_pending_count": 5,
        "session_id": 12,
    }

    text = formatter.format_crawl_result(result)
    rows = formatter.results_to_csv_rows([result])

    assert "total_ips" in text
    assert "avg_confidence" in text
    assert "ai_calls_count" in text
    assert "llm_cost_usd" in text
    assert "review_pending" in text
    assert rows[0]["total_ips"] == 125
    assert rows[0]["review_pending_count"] == 5
