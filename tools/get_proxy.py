import argparse
import json
from typing import List, Optional

from crawler.proxy_picker import pick_proxies
from crawler.runtime import load_settings
from crawler.storage import set_settings_for_retry


def _parse_csv(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    cleaned = [part for part in parts if part]
    return cleaned or None


def add_arguments(parser: argparse.ArgumentParser) -> None:
    # CLI 参数统一注册，便于主入口复用
    parser.add_argument("--protocol", help="Comma-separated protocols, e.g. http,https")
    parser.add_argument("--country", help="Comma-separated countries, e.g. US,CN")
    parser.add_argument("--count", type=int, default=1, help="Number of proxies to return")
    parser.add_argument("--check-url", help="URL used for HTTP/HTTPS validation")
    parser.add_argument("--no-check", action="store_true", help="Disable validation checks")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pick proxies from the pool")
    add_arguments(parser)
    return parser


def run_from_args(args: argparse.Namespace, env_path: Optional[str] = None) -> int:
    # 根据参数执行选取逻辑并输出 JSON
    settings = load_settings(env_path)
    set_settings_for_retry(settings)
    
    protocols = _parse_csv(args.protocol)
    countries = _parse_csv(args.country)
    require_check = not args.no_check

    try:
        result = pick_proxies(
            settings,
            protocols=protocols,
            countries=countries,
            count=args.count,
            check_url=args.check_url,
            require_check=require_check,
        )
    except Exception as exc:
        result = {"status": "error", "message": f"{type(exc).__name__}: {exc}", "data": None}
        print(json.dumps(result, ensure_ascii=True))
        return 1

    print(json.dumps(result, ensure_ascii=True))
    return 0


def run(argv: Optional[List[str]] = None) -> int:
    # 独立脚本入口，保持向后兼容
    parser = _build_parser()
    args = parser.parse_args(argv)
    return run_from_args(args)


if __name__ == "__main__":
    raise SystemExit(run())
