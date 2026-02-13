from pathlib import Path

from crawler.parsers import (
    parse_geonode,
    parse_proxy_list_download_http,
)


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_parse_proxy_list_download_http():
    text = (FIXTURES_DIR / "proxy-list-download.txt").read_text(encoding="utf-8")
    records = parse_proxy_list_download_http(text)
    assert len(records) == 2
    assert records[0]["ip"] == "2.2.2.2"


def test_parse_geonode():
    text = (FIXTURES_DIR / "geonode.json").read_text(encoding="utf-8")
    records = parse_geonode(text)
    assert len(records) == 2
    protocols = {r["protocol"] for r in records}
    assert protocols == {"http", "https"}


def test_parse_geonode_invalid_json_returns_empty():
    records = parse_geonode("not json")
    assert records == []
