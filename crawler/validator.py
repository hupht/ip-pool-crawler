import socket
import time
from typing import Dict, List, Tuple


class Validator:
    def __init__(self, suspicious_threshold: float = 0.5):
        self.suspicious_threshold = float(max(0.0, min(1.0, suspicious_threshold)))

    @staticmethod
    def validate_ip(ip: str) -> bool:
        if not ip:
            return False
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            numbers = [int(p) for p in parts]
        except ValueError:
            return False
        return all(0 <= n <= 255 for n in numbers)

    @staticmethod
    def validate_port(port: int) -> bool:
        try:
            value = int(port)
        except (ValueError, TypeError):
            return False
        return 1 <= value <= 65535

    @staticmethod
    def validate_table_structure(table: object) -> Tuple[bool, str]:
        headers = getattr(table, "headers", []) or []
        rows = getattr(table, "rows", []) or []

        if not headers and not rows:
            return False, "empty table"

        if headers:
            expected_columns = len(headers)
            for index, row in enumerate(rows):
                if abs(len(row) - expected_columns) > 1:
                    return False, f"row {index} column count mismatch"

        return True, "ok"

    @staticmethod
    def validate_page_coverage(records: List[dict], expected: int) -> float:
        expected_count = max(0, int(expected))
        if expected_count == 0:
            return 1.0 if not records else 0.0
        return min(1.0, max(0.0, len(records) / expected_count))

    def mark_suspicious_data(self, record: dict) -> dict:
        data = dict(record)
        ip = data.get("ip")
        port = data.get("port")
        confidence = float(data.get("confidence", 1.0))

        reasons: List[str] = []
        if not self.validate_ip(str(ip or "")):
            reasons.append("invalid_ip")
        if not self.validate_port(port):
            reasons.append("invalid_port")
        if confidence < self.suspicious_threshold:
            reasons.append("low_confidence")

        data["is_suspicious"] = len(reasons) > 0
        data["suspicious_reasons"] = reasons
        return data


def tcp_check(host: str, port: int, timeout: int = 2) -> Tuple[bool, int]:
    # TCP 探测并返回延迟毫秒
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = int((time.time() - start) * 1000)
            return True, latency_ms
    except OSError:
        return False, 0


def score_proxy(latency_ms: int, success: bool) -> int:
    # 简单评分：成功则按延迟扣分
    if not success:
        return 0
    return max(1, 10000 - latency_ms)
