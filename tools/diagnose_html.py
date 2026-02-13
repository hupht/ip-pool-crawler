import re

import requests
from bs4 import BeautifulSoup

URLS = [
    "https://www.free-proxy-list.net/",
    "https://www.sslproxies.org/",
    "https://www.us-proxy.org/",
    "https://www.geonode.com/free-proxy-list/",
]


def run() -> None:
    # 检查页面结构是否存在目标表格与反爬痕迹
    for url in URLS:
        try:
            resp = requests.get(url, timeout=10)
            text = resp.text
            soup = BeautifulSoup(text, "html.parser")
            table = soup.find("table", id="proxylisttable")
            rows = 0
            if table:
                rows = len(table.find_all("tr"))
            has_cloudflare = bool(re.search(r"cloudflare|cf-challenge|captcha", text, re.I))
            print(
                f"{url} status={resp.status_code} len={len(text)} table={bool(table)} rows={rows} cloudflare={has_cloudflare}"
            )
        except Exception as exc:
            print(f"{url} ERROR {type(exc).__name__} {exc}")


if __name__ == "__main__":
    run()
