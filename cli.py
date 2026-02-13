from __future__ import annotations

import argparse
import csv
import importlib.util
from pathlib import Path

from crawler.dynamic_crawler import DynamicCrawler, crawl_custom_url
from crawler.pipeline import run_once
from crawler.runtime import load_settings
from tools import check_docs_links, check_pool, diagnose_html, diagnose_pipeline, diagnose_sources, get_proxy, redis_ping
import verify_deploy


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{prompt} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "1", "true"}


def _prompt_int(prompt: str, default: int) -> int:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _format_crawl_custom_result(result: object) -> str:
    formatter_path = Path(__file__).resolve().parent / "cli" / "result_formatter.py"
    if not formatter_path.exists():
        return str(result)

    spec = importlib.util.spec_from_file_location("result_formatter", formatter_path)
    if spec is None or spec.loader is None:
        return str(result)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "format_crawl_result"):
        return module.format_crawl_result(result)
    return str(result)


def _export_crawl_custom_result(result: object, json_path: str | None, csv_path: str | None) -> None:
    if not json_path and not csv_path:
        return

    formatter_path = Path(__file__).resolve().parent / "cli" / "result_formatter.py"
    if not formatter_path.exists():
        return

    spec = importlib.util.spec_from_file_location("result_formatter", formatter_path)
    if spec is None or spec.loader is None:
        return

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if json_path and hasattr(module, "result_to_json"):
        json_text = module.result_to_json(result)
        Path(json_path).write_text(json_text, encoding="utf-8")

    if csv_path and hasattr(module, "results_to_csv_rows"):
        rows = module.results_to_csv_rows([result])
        output_path = Path(csv_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if rows:
            with output_path.open("w", encoding="utf-8", newline="") as fp:
                writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        else:
            output_path.write_text("", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    # 统一命令行入口，避免各脚本分散调用
    parser = argparse.ArgumentParser(description="IP pool crawler CLI")
    parser.add_argument("--env", help="Path to .env file")

    # 子命令分流
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one crawler cycle")
    run_parser.add_argument(
        "--quick-test",
        action="store_true",
        help="Quick mode for testing: stop after first source with parsable records",
    )
    run_parser.add_argument(
        "--quick-record-limit",
        type=int,
        default=1,
        help="In quick-test mode, process at most N records from the first successful source",
    )
    crawl_custom_parser = subparsers.add_parser("crawl-custom", help="Crawl one custom URL")
    crawl_custom_parser.add_argument("url", nargs="?", help="Target URL to crawl")
    crawl_custom_parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages to crawl")
    crawl_custom_parser.add_argument("--use-ai", action="store_true", help="Enable AI fallback")
    crawl_custom_parser.add_argument("--render-js", action="store_true", help="Render page via Playwright before parsing")
    crawl_custom_parser.add_argument("--no-store", action="store_true", help="Do not store to MySQL")
    crawl_custom_parser.add_argument("--verbose", action="store_true", help="Verbose output")
    crawl_custom_parser.add_argument("--output-json", type=str, default=None, help="Export crawl result to JSON file")
    crawl_custom_parser.add_argument("--output-csv", type=str, default=None, help="Export crawl result to CSV file")
    subparsers.add_parser("check", help="Run TCP check batch")

    # 复用 get_proxy 的参数定义，保证一致性
    get_parser = subparsers.add_parser("get-proxy", help="Pick proxies from the pool")
    get_proxy.add_arguments(get_parser)

    subparsers.add_parser("diagnose-sources", help="Check raw source availability")
    subparsers.add_parser("diagnose-pipeline", help="Fetch and parse source data")
    subparsers.add_parser("diagnose-html", help="Check HTML parsing hints")
    subparsers.add_parser("redis-ping", help="Ping Redis with current settings")
    subparsers.add_parser("verify-deploy", help="Run lightweight deployment verification")
    check_docs_parser = subparsers.add_parser(
        "check-docs-links",
        help="Validate docs markdown links and anchors (local/CI)",
    )
    check_docs_parser.add_argument(
        "--docs-dir",
        default="docs",
        help="Docs directory relative to project root (default: docs)",
    )
    check_docs_parser.add_argument(
        "--max-errors",
        type=int,
        default=100,
        help="Maximum broken links to print (default: 100)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        # 运行完整抓取流程
        settings = load_settings(args.env)
        run_once(
            settings,
            quick_test=args.quick_test,
            quick_record_limit=args.quick_record_limit,
        )
        return 0

    if args.command == "crawl-custom":
        settings = load_settings(args.env)
        if not settings.dynamic_crawler_enabled:
            parser.error("DYNAMIC_CRAWLER_ENABLED=false，已禁用 crawl-custom")

        target_url = args.url
        max_pages = args.max_pages if args.max_pages is not None else settings.max_pages
        use_ai = args.use_ai or settings.use_ai_fallback
        render_js = args.render_js
        no_store = args.no_store

        if not target_url:
            print("欢迎使用通用动态爬虫交互模式")
            target_url = input("请输入网址: ").strip()
            if not target_url:
                parser.error("URL 不能为空")
            max_pages = _prompt_int("最大页数", settings.max_pages)
            use_ai = _prompt_yes_no("启用 AI 辅助", default=settings.use_ai_fallback)
            render_js = _prompt_yes_no("启用 JS 渲染抓取(Playwright)", default=False)
            auto_store = _prompt_yes_no("自动存储到 MySQL", default=True)
            no_store = not auto_store

        result = crawl_custom_url(
            settings=settings,
            url=target_url,
            max_pages=max_pages,
            use_ai=use_ai,
            no_store=no_store,
            verbose=args.verbose,
            render_js=render_js,
        )

        result_payload: object = result
        session_id = getattr(result, "session_id", None)
        if session_id is not None:
            try:
                crawler = DynamicCrawler(settings)
                session_stats = crawler.get_session_stats(int(session_id))
                result_dict = dict(vars(result))
                result_dict["total_ips"] = session_stats.get("ip_count", result_dict.get("extracted", 0))
                result_dict["avg_confidence"] = session_stats.get("avg_extraction_confidence", 0.0)
                result_dict["ai_calls_count"] = session_stats.get("llm_calls", 0)
                result_dict["llm_cost_usd"] = session_stats.get("llm_cost_usd", 0.0)
                result_dict["review_pending_count"] = session_stats.get("review_pending_count", 0)
                result_payload = result_dict
            except Exception:
                result_payload = result

        print(_format_crawl_custom_result(result_payload))
        _export_crawl_custom_result(result_payload, args.output_json, args.output_csv)

        if not no_store and result.stored > 0:
            print("检测到已入库代理，自动执行 TCP 检查批处理...")
            check_pool.run_check_batch(settings)
        return 0

    if args.command == "check":
        # 只执行批量 TCP 检测
        settings = load_settings(args.env)
        check_pool.run_check_batch(settings)
        return 0

    if args.command == "get-proxy":
        # 代理挑选结果以 JSON 输出
        return get_proxy.run_from_args(args, env_path=args.env)

    if args.command == "diagnose-sources":
        diagnose_sources.run()
        return 0

    if args.command == "diagnose-pipeline":
        diagnose_pipeline.run()
        return 0

    if args.command == "diagnose-html":
        diagnose_html.run()
        return 0

    if args.command == "redis-ping":
        redis_ping.run()
        return 0

    if args.command == "verify-deploy":
        return verify_deploy.main(env_path=args.env)

    if args.command == "check-docs-links":
        root = Path(__file__).resolve().parent
        return check_docs_links.main(
            [
                "--root",
                str(root),
                "--docs-dir",
                str(args.docs_dir),
                "--max-errors",
                str(args.max_errors),
            ]
        )

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
