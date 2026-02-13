from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional

import requests


@dataclass
class HTTPValidationResult:
    is_reachable: bool
    status_code: Optional[int]
    response_time_ms: int
    protocol_verified: bool
    errors: List[str] = field(default_factory=list)


class HTTPValidator:
    TEST_URL = "https://httpbin.org/ip"
    SUPPORTED_PROTOCOLS = {"http", "https", "socks4", "socks5", "socks4a"}

    @staticmethod
    def validate_with_http(ip: str, port: int, protocol: str = "http", timeout: int = 3) -> HTTPValidationResult:
        normalized_protocol = (protocol or "http").strip().lower()

        if normalized_protocol not in HTTPValidator.SUPPORTED_PROTOCOLS:
            return HTTPValidationResult(
                is_reachable=False,
                status_code=None,
                response_time_ms=0,
                protocol_verified=False,
                errors=[f"unsupported protocol: {normalized_protocol}"],
            )

        proxy_url = f"{normalized_protocol}://{ip}:{port}"
        proxies: Dict[str, str] = {"http": proxy_url, "https": proxy_url}

        start = time.time()
        try:
            response = requests.get(HTTPValidator.TEST_URL, proxies=proxies, timeout=timeout)
            elapsed_ms = int((time.time() - start) * 1000)
            status_code = response.status_code
            return HTTPValidationResult(
                is_reachable=200 <= status_code < 400,
                status_code=status_code,
                response_time_ms=elapsed_ms,
                protocol_verified=True,
                errors=[],
            )
        except requests.RequestException as exc:
            elapsed_ms = int((time.time() - start) * 1000)
            return HTTPValidationResult(
                is_reachable=False,
                status_code=None,
                response_time_ms=elapsed_ms,
                protocol_verified=False,
                errors=[str(exc)],
            )

    @staticmethod
    def batch_validate(proxies: List[Dict[str, object]], timeout: int = 3) -> List[HTTPValidationResult]:
        results: List[HTTPValidationResult] = []
        for proxy in proxies:
            ip = str(proxy.get("ip", ""))
            port = int(proxy.get("port", 0))
            protocol = str(proxy.get("protocol", "http"))
            results.append(HTTPValidator.validate_with_http(ip, port, protocol, timeout=timeout))
        return results
