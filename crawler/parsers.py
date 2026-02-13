import json
from typing import Dict, List

from bs4 import BeautifulSoup


Record = Dict[str, object]


def _parse_proxy_table(html: str) -> List[Record]:
    # 解析带表格的 HTML 代理列表
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="proxylisttable")
    if not table:
        return []

    records: List[Record] = []
    for row in table.find_all("tr"):
        cells = [cell.get_text(strip=True) for cell in row.find_all("td")]
        if len(cells) < 7:
            continue
        ip, port, _code, country, anonymity, _google, https = cells[:7]
        protocol = "https" if https.lower() == "yes" else "http"
        records.append(
            {
                "ip": ip,
                "port": int(port),
                "protocol": protocol,
                "anonymity": anonymity,
                "country": country,
            }
        )
    return records


def parse_free_proxy_list(html: str) -> List[Record]:
    return _parse_proxy_table(html)


def parse_sslproxies(html: str) -> List[Record]:
    return _parse_proxy_table(html)


def parse_us_proxy(html: str) -> List[Record]:
    return _parse_proxy_table(html)


def _parse_proxy_list_download(text: str, protocol: str) -> List[Record]:
    # 解析 proxy-list.download 的纯文本列表
    records: List[Record] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        ip, port = line.split(":", 1)
        records.append({"ip": ip, "port": int(port), "protocol": protocol})
    return records


def parse_proxy_list_download_http(text: str) -> List[Record]:
    return _parse_proxy_list_download(text, "http")


def parse_proxy_list_download_https(text: str) -> List[Record]:
    return _parse_proxy_list_download(text, "https")


def parse_proxy_list_download_socks4(text: str) -> List[Record]:
    return _parse_proxy_list_download(text, "socks4")


def parse_proxy_list_download_socks5(text: str) -> List[Record]:
    return _parse_proxy_list_download(text, "socks5")


def parse_geonode(text: str) -> List[Record]:
    # 解析 geonode JSON 数据
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    data = payload.get("data", [])
    records: List[Record] = []
    for item in data:
        ip = item.get("ip")
        port = item.get("port")
        protocols = item.get("protocols") or ["http"]
        country = item.get("country")
        anonymity = item.get("anonymityLevel")
        for protocol in protocols:
            records.append(
                {
                    "ip": ip,
                    "port": int(port),
                    "protocol": protocol,
                    "country": country,
                    "anonymity": anonymity,
                }
            )
    return records
