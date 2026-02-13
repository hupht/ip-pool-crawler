from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    parser_key: str


def get_sources() -> List[Source]:
    # 代理来源配置列表
    return [
        Source(
            name="proxy-list-download-http",
            url="https://www.proxy-list.download/api/v1/get?type=http",
            parser_key="proxy_list_download_http",
        ),
        Source(
            name="proxy-list-download-https",
            url="https://www.proxy-list.download/api/v1/get?type=https",
            parser_key="proxy_list_download_https",
        ),
        Source(
            name="proxy-list-download-socks4",
            url="https://www.proxy-list.download/api/v1/get?type=socks4",
            parser_key="proxy_list_download_socks4",
        ),
        Source(
            name="proxy-list-download-socks5",
            url="https://www.proxy-list.download/api/v1/get?type=socks5",
            parser_key="proxy_list_download_socks5",
        ),
        Source(
            name="geonode",
            url="https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc",
            parser_key="geonode",
        ),
    ]
