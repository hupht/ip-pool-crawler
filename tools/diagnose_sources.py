import requests

URLS = [
    "https://www.free-proxy-list.net/",
    "https://www.sslproxies.org/",
    "https://www.us-proxy.org/",
    "https://www.proxy-list.download/",
    "https://www.geonode.com/free-proxy-list/",
]


def run() -> None:
    # 仅检查源站可用性与响应大小
    for url in URLS:
        try:
            resp = requests.get(url, timeout=10)
            print(f"{url} {resp.status_code} {len(resp.text)}")
        except Exception as exc:
            print(f"{url} ERROR {type(exc).__name__} {exc}")


if __name__ == "__main__":
    run()
