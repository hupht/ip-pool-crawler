import json
from dataclasses import asdict
from typing import Any, Dict, Iterable, List


def _to_result_dict(result: Any) -> Dict[str, Any]:
    if hasattr(result, "__dataclass_fields__"):
        return asdict(result)
    if isinstance(result, dict):
        return dict(result)
    return {"value": str(result)}


def format_crawl_result_table(result: Any) -> str:
    data = _to_result_dict(result)
    if "url" not in data:
        return str(result)

    rows = [
        ("url", data.get("url", "")),
        ("pages_crawled", data.get("pages_crawled", 0)),
        ("total_ips", data.get("total_ips", data.get("extracted", 0))),
        ("extracted", data.get("extracted", 0)),
        ("valid", data.get("valid", 0)),
        ("invalid", data.get("invalid", 0)),
        ("stored", data.get("stored", 0)),
        ("avg_confidence", f"{float(data.get('avg_confidence', 0.0)):.2f}"),
        ("ai_calls_count", data.get("ai_calls_count", 0)),
        ("llm_cost_usd", f"{float(data.get('llm_cost_usd', 0.0)):.6f}"),
        ("review_pending", data.get("review_pending_count", 0)),
    ]
    if data.get("session_id") is not None:
        rows.append(("session_id", data.get("session_id")))

    key_width = max(len(k) for k, _ in rows)
    val_width = max(len(str(v)) for _, v in rows)
    border = f"+{'-' * (key_width + 2)}+{'-' * (val_width + 2)}+"

    lines = ["crawl-custom 结果", border]
    for key, value in rows:
        lines.append(f"| {key.ljust(key_width)} | {str(value).ljust(val_width)} |")
    lines.append(border)
    return "\n".join(lines)


def format_crawl_result(result: Any) -> str:
    return format_crawl_result_table(result)


def result_to_json(result: Any, ensure_ascii: bool = False) -> str:
    data = _to_result_dict(result)
    return json.dumps(data, ensure_ascii=ensure_ascii)


def results_to_csv_rows(results: Iterable[Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in results:
        data = _to_result_dict(result)
        rows.append(
            {
                "url": data.get("url", ""),
                "pages_crawled": data.get("pages_crawled", 0),
                "total_ips": data.get("total_ips", data.get("extracted", 0)),
                "extracted": data.get("extracted", 0),
                "valid": data.get("valid", 0),
                "invalid": data.get("invalid", 0),
                "stored": data.get("stored", 0),
                "avg_confidence": data.get("avg_confidence", 0.0),
                "ai_calls_count": data.get("ai_calls_count", 0),
                "llm_cost_usd": data.get("llm_cost_usd", 0.0),
                "review_pending_count": data.get("review_pending_count", 0),
                "session_id": data.get("session_id"),
            }
        )
    return rows
