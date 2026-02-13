from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Tuple

import requests

from crawler.config import Settings
from crawler.sources import Source


def fetch_source(source: Source, settings: Settings) -> Tuple[str, int]:
    # 带重试的抓取，避免单次网络波动导致失败
    headers = {"User-Agent": settings.user_agent}
    attempts = max(1, settings.http_retries + 1)
    for attempt in range(attempts):
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    requests.get,
                    source.url,
                    headers=headers,
                    timeout=settings.http_timeout,
                )
                response = future.result(timeout=settings.http_timeout + 2)
            response.raise_for_status()
            return response.text, response.status_code
        except (FutureTimeout, Exception):
            if attempt == attempts - 1:
                return "", 0
    return "", 0
