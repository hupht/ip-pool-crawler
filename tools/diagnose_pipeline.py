from crawler.fetcher import fetch_source
from crawler.parsers import (
    parse_geonode,
    parse_proxy_list_download_http,
    parse_proxy_list_download_https,
    parse_proxy_list_download_socks4,
    parse_proxy_list_download_socks5,
)
from crawler.runtime import load_settings
from crawler.sources import get_sources

PARSERS = {
    "proxy_list_download_http": parse_proxy_list_download_http,
    "proxy_list_download_https": parse_proxy_list_download_https,
    "proxy_list_download_socks4": parse_proxy_list_download_socks4,
    "proxy_list_download_socks5": parse_proxy_list_download_socks5,
    "geonode": parse_geonode,
}


def run() -> None:
    # 逐个源站抓取并解析，便于排查解析失败
    settings = load_settings()
    for source in get_sources():
        raw, status = fetch_source(source, settings)
        parser = PARSERS.get(source.parser_key)
        if not raw:
            print(f"{source.name}: fetch failed (status={status})")
            continue
        try:
            records = parser(raw) if parser else []
            print(f"{source.name}: status={status}, records={len(records)}")
        except Exception as exc:
            print(f"{source.name}: parse error {type(exc).__name__} {exc}")


if __name__ == "__main__":
    run()
