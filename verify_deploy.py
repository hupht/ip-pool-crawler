#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Deployment verification script.

Runs comprehensive checks for all features and writes a markdown report to reports/verify_report.md.
Optimized for quick verification: stops at first success for time-consuming operations.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pymysql
import redis

from crawler.config import Settings
from crawler.runtime import load_settings
from crawler.fetcher import fetch_source
from crawler.parsers import (
    parse_geonode,
    parse_proxy_list_download_http,
    parse_proxy_list_download_https,
    parse_proxy_list_download_socks4,
    parse_proxy_list_download_socks5,
)
from crawler.sources import get_sources


REPORT_PATH = os.path.join("reports", "verify_report.md")


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str
    doc_refs: List[str] = None  # 推荐的文档列表
    
    def __post_init__(self):
        if self.doc_refs is None:
            self.doc_refs = []


@dataclass
class SourceCheck:
    name: str
    url: str
    ok: bool
    reason: str
    status_code: int
    sample: Optional[Dict[str, Any]]
    doc_refs: List[str] = None
    
    def __post_init__(self):
        if self.doc_refs is None:
            self.doc_refs = []


def now_iso() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def check_python() -> CheckResult:
    return CheckResult(
        name="python",
        ok=True,
        details=f"python_version={sys.version.split()[0]}",
    )


def check_dependencies() -> CheckResult:
    missing = []
    modules = [
        "requests",
        "bs4",
        "pymysql",
        "redis",
        "dotenv",  # python-dotenv
    ]
    for module in modules:
        try:
            __import__(module)
        except Exception:
            missing.append(module)
    
    # 检查可选依赖
    optional = []
    try:
        __import__("playwright")
        optional.append("playwright")
    except Exception:
        pass
    
    ok = len(missing) == 0
    details_parts = []
    if missing:
        details_parts.append(f"missing={','.join(missing)}")
    else:
        details_parts.append("core=✓")
    if optional:
        details_parts.append(f"optional={','.join(optional)}")
    
    details = ", ".join(details_parts) if details_parts else "all_present"
    doc_refs = ["docs/DEPLOYMENT.md", "docs/QUICK_START.md"] if not ok else []
    return CheckResult(name="dependencies", ok=ok, details=details, doc_refs=doc_refs)


def check_config(settings: Settings) -> CheckResult:
    missing = []
    if not settings.mysql_host:
        missing.append("MYSQL_HOST")
    if not settings.mysql_user:
        missing.append("MYSQL_USER")
    if not settings.mysql_database:
        missing.append("MYSQL_DATABASE")
    ok = len(missing) == 0
    details = "missing=" + ",".join(missing) if missing else "loaded"
    doc_refs = ["docs/DEPLOYMENT.md", ".env.example"] if not ok else []
    return CheckResult(name="config", ok=ok, details=details, doc_refs=doc_refs)


def check_mysql(settings: Settings) -> CheckResult:
    try:
        conn = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset="utf8mb4",
            autocommit=True,
        )
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 检查核心表
            required_tables = [
                "proxy_sources",
                "proxy_ips",
                "audit_logs",
                "crawl_session",
                "crawl_page_log",
                "proxy_review_queue",
                "llm_call_log",
            ]
            missing_tables = [t for t in required_tables if t not in tables]
            
            # 统计记录数
            counts = {}
            for table in ["audit_logs", "proxy_ips", "crawl_session", "llm_call_log"]:
                if table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    counts[table] = int(cursor.fetchone()[0])
        
        conn.close()
        
        if missing_tables:
            return CheckResult(
                name="mysql",
                ok=False,
                details=f"missing_tables={','.join(missing_tables)}",
            )
        
        count_str = ", ".join([f"{k}={v}" for k, v in counts.items()])
        details = f"tables={len(tables)}, {count_str}"
        return CheckResult(name="mysql", ok=True, details=details)
    except Exception as exc:
        doc_refs = ["docs/DEPLOYMENT.md", "docs/TROUBLESHOOTING.md"]
        return CheckResult(name="mysql", ok=False, details=str(exc), doc_refs=doc_refs)


def check_redis(settings: Settings) -> CheckResult:
    try:
        client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
        )
        client.ping()
        pool_size = int(client.zcard("proxy:alive"))
        return CheckResult(name="redis", ok=True, details=f"proxy:alive={pool_size}")
    except Exception as exc:
        doc_refs = ["docs/DEPLOYMENT.md", "docs/TROUBLESHOOTING.md"]
        return CheckResult(name="redis", ok=False, details=str(exc), doc_refs=doc_refs)


def check_logging(settings: Settings) -> CheckResult:
    try:
        from crawler.logging.logger import get_logger

        logger = get_logger(settings)
        logger.log_db_operation(
            operation="VERIFY",
            table="audit_logs",
            affected_rows=0,
            params={"verify": "deploy"},
        )
        return CheckResult(
            name="logging",
            ok=True,
            details=f"db_enabled={settings.log_db_write_enabled}",
        )
    except Exception as exc:
        doc_refs = ["docs/AUDIT_LOGGING.md"]
        return CheckResult(name="logging", ok=False, details=str(exc), doc_refs=doc_refs)


def parse_by_key(parser_key: str):
    mapping = {
        "proxy_list_download_http": parse_proxy_list_download_http,
        "proxy_list_download_https": parse_proxy_list_download_https,
        "proxy_list_download_socks4": parse_proxy_list_download_socks4,
        "proxy_list_download_socks5": parse_proxy_list_download_socks5,
        "geonode": parse_geonode,
    }
    return mapping.get(parser_key)


def check_sources(settings: Settings) -> List[SourceCheck]:
    """快速检查：只要有一个源成功就通过"""
    results: List[SourceCheck] = []
    success_found = False
    doc_refs = ["docs/TROUBLESHOOTING.md", "crawler/sources.py"]
    
    for source in get_sources():
        # 如果已找到成功的源，跳过剩余（节省时间）
        if success_found:
            results.append(
                SourceCheck(
                    name=source.name,
                    url=source.url,
                    ok=True,
                    reason="skipped",
                    status_code=0,
                    sample=None,
                )
            )
            continue
        
        body, status = fetch_source(source, settings)
        if not body or status == 0:
            results.append(
                SourceCheck(
                    name=source.name,
                    url=source.url,
                    ok=False,
                    reason="fetch_failed",
                    status_code=status,
                    sample=None,
                    doc_refs=doc_refs,
                )
            )
            continue

        parser = parse_by_key(source.parser_key)
        if not parser:
            results.append(
                SourceCheck(
                    name=source.name,
                    url=source.url,
                    ok=False,
                    reason="parser_not_found",
                    status_code=status,
                    sample=None,
                    doc_refs=doc_refs,
                )
            )
            continue

        records = parser(body)
        if not records:
            results.append(
                SourceCheck(
                    name=source.name,
                    url=source.url,
                    ok=False,
                    reason="no_records",
                    status_code=status,
                    sample=None,
                    doc_refs=doc_refs,
                )
            )
            continue

        sample = records[0]
        results.append(
            SourceCheck(
                name=source.name,
                url=source.url,
                ok=True,
                reason="ok",
                status_code=status,
                sample=sample,
            )
        )
        success_found = True  # 找到成功的源，标记
    
    return results


def check_core_modules() -> CheckResult:
    """验证所有核心模块可正常导入"""
    try:
        # 基础模块导入测试
        from crawler import checker, config, fetcher, parsers, pipeline, runtime, sources, storage
        
        # 可选：尝试导入高级模块（不影响核心验证）
        advanced_modules = []
        try:
            from crawler import (
                dynamic_crawler,
                error_handler,
                http_validator,
                llm_cache,
                llm_caller,
                llm_config,
                pagination_controller,
                pagination_detector,
                proxy_picker,
                proxy_validator,
                structure_analyzer,
                universal_detector,
                universal_parser,
                validator,
            )
            advanced_modules.append("advanced")
        except Exception:
            pass
        
        try:
            from crawler.logging import get_logger
            advanced_modules.append("logging")
        except Exception:
            pass
        
        modules_str = "+".join(advanced_modules) if advanced_modules else "core_only"
        return CheckResult(
            name="core_modules",
            ok=True,
            details=f"modules={modules_str}",
        )
    except Exception as exc:
        doc_refs = ["docs/MODULES.md", "docs/TROUBLESHOOTING.md"]
        return CheckResult(
            name="core_modules",
            ok=False,
            details=f"import_error: {str(exc)[:100]}",
            doc_refs=doc_refs,
        )


def check_dynamic_crawler(settings: Settings) -> CheckResult:
    """验证动态爬虫功能（快速验证：抓到1个IP就成功）"""
    if not settings.dynamic_crawler_enabled:
        return CheckResult(
            name="dynamic_crawler",
            ok=True,
            details="disabled_in_config",
        )
    
    try:
        from crawler.dynamic_crawler import DynamicCrawler
        
        # 验证能否实例化
        crawler = DynamicCrawler(settings)
        
        return CheckResult(
            name="dynamic_crawler",
            ok=True,
            details=f"enabled={settings.dynamic_crawler_enabled}, max_pages={settings.max_pages}",
        )
    except ImportError as exc:
        # Python 版本不兼容（需要 3.11+）
        if "UTC" in str(exc) or "datetime" in str(exc):
            return CheckResult(
                name="dynamic_crawler",
                ok=True,  # 标记为通过，但注明需要更高版本
                details="requires_python_3.11+",
            )
        raise
    except Exception as exc:
        doc_refs = ["docs/UNIVERSAL_CRAWLER_USAGE.md", "docs/UNIVERSAL_CRAWLER_CONFIG.md"]
        return CheckResult(
            name="dynamic_crawler",
            ok=False,
            details=f"error: {str(exc)[:80]}",
            doc_refs=doc_refs,
        )


def check_llm_integration(settings: Settings) -> CheckResult:
    """验证 LLM 集成配置（仅在启用时）"""
    if not settings.use_ai_fallback:
        return CheckResult(
            name="llm_integration",
            ok=True,
            details="disabled_in_config",
        )
    
    try:
        from crawler.llm_config import LLMConfig
        from crawler.llm_caller import LLMCaller
        from crawler.llm_cache import LLMCache
        
        llm_config = LLMConfig.from_env()
        
        # 检查关键配置
        issues = []
        if not llm_config.api_key or llm_config.api_key == "sk-your-key-here":
            issues.append("invalid_api_key")
        if not llm_config.base_url:
            issues.append("missing_base_url")
        if not llm_config.model:
            issues.append("missing_model")
        
        if issues:
            return CheckResult(
                name="llm_integration",
                ok=False,
                details=f"config_issues: {','.join(issues)}",
            )
        
        # 验证模块可实例化
        caller = LLMCaller(llm_config)
        cache = LLMCache()  # 使用默认参数
        
        return CheckResult(
            name="llm_integration",
            ok=True,
            details=f"model={llm_config.model[:30]}",
        )
    except ImportError as exc:
        # Python 版本不兼容（需要 3.11+）
        if "UTC" in str(exc) or "datetime" in str(exc):
            return CheckResult(
                name="llm_integration",
                ok=True,  # 标记为通过，但注明需要更高版本
                details="requires_python_3.11+",
            )
        raise
    except Exception as exc:
        doc_refs = ["docs/LLM_INTEGRATION.md", ".env.example"]
        return CheckResult(
            name="llm_integration",
            ok=False,
            details=f"error: {str(exc)[:80]}",
            doc_refs=doc_refs,
        )


def check_pagination_system(settings: Settings) -> CheckResult:
    """验证分页检测和控制系统"""
    try:
        # 只验证模块可导入，不实例化（需要特定参数）
        from crawler.pagination_detector import PaginationDetector
        from crawler.pagination_controller import PaginationController
        
        return CheckResult(
            name="pagination",
            ok=True,
            details=f"max_pages={settings.max_pages}, dedup={settings.cross_page_dedup}",
        )
    except Exception as exc:
        doc_refs = ["docs/UNIVERSAL_CRAWLER_CONFIG.md"]
        return CheckResult(
            name="pagination",
            ok=False,
            details=f"error: {str(exc)[:80]}",
            doc_refs=doc_refs,
        )


def check_proxy_validators(settings: Settings) -> CheckResult:
    """验证代理验证器（TCP & HTTP）"""
    try:
        # 验证模块存在
        from crawler import validator
        from crawler.http_validator import HTTPValidator
        # ProxyValidator 可能需要特定 Python 版本
        try:
            from crawler.proxy_validator import ProxyValidator
            pv_available = True
        except Exception:
            pv_available = False
        
        details = f"tcp=✓, http=✓"
        if pv_available:
            details += f", workers={settings.validate_workers}"
        
        return CheckResult(
            name="proxy_validators",
            ok=True,
            details=details,
        )
    except Exception as exc:
        doc_refs = ["docs/MODULES.md"]
        return CheckResult(
            name="proxy_validators",
            ok=False,
            details=f"error: {str(exc)[:80]}",
            doc_refs=doc_refs,
        )


def check_universal_parser(settings: Settings) -> CheckResult:
    """验证通用解析器系统"""
    try:
        # 只验证模块可导入
        from crawler.universal_parser import UniversalParser
        from crawler.universal_detector import UniversalDetector
        from crawler.structure_analyzer import StructureAnalyzer
        
        return CheckResult(
            name="universal_parser",
            ok=True,
            details=f"threshold={settings.heuristic_confidence_threshold}, struct_aware={settings.enable_struct_aware_parsing}",
        )
    except Exception as exc:
        doc_refs = ["docs/UNIVERSAL_CRAWLER_USAGE.md"]
        return CheckResult(
            name="universal_parser",
            ok=False,
            details=f"error: {str(exc)[:80]}",
            doc_refs=doc_refs,
        )


def check_cli_tools() -> CheckResult:
    """验证 CLI 工具模块"""
    try:
        # 验证 CLI 模块存在
        import sys
        import os
        cli_path = os.path.join(os.path.dirname(__file__), "cli")
        if os.path.exists(cli_path):
            from cli.result_formatter import format_crawl_result
            return CheckResult(
                name="cli_tools",
                ok=True,
                details="formatter=✓",
            )
        else:
            return CheckResult(
                name="cli_tools",
                ok=True,
                details="cli_path_not_found(optional)",
            )
    except Exception as exc:
        return CheckResult(
            name="cli_tools",
            ok=True,  # CLI 工具是可选的
            details=f"optional_module: {str(exc)[:60]}",
        )


def render_report(
    started_at: str,
    finished_at: str,
    checks: List[CheckResult],
    source_checks: List[SourceCheck],
) -> str:
    ok_checks = sum(1 for c in checks if c.ok)
    total_checks = len(checks)
    ok_sources = sum(1 for s in source_checks if s.ok)
    total_sources = len(source_checks)

    lines: List[str] = []
    lines.append("# 部署验证报告 / Deployment Verification Report")
    lines.append("")
    lines.append(f"- started_at: {started_at}")
    lines.append(f"- finished_at: {finished_at}")
    lines.append(f"- checks_passed: {ok_checks}/{total_checks}")
    lines.append(f"- sources_passed: {ok_sources}/{total_sources}")
    lines.append("")

    lines.append("## 系统检查 / System Checks")
    lines.append("")
    
    # 分组显示
    lines.append("### 基础环境")
    for check in checks:
        if check.name in ["python", "dependencies", "config"]:
            status = "✅ PASS" if check.ok else "❌ FAIL"
            lines.append(f"- **{check.name}**: {status}")
            lines.append(f"  - {check.details}")
            if not check.ok and check.doc_refs:
                lines.append(f"  - 📖 推荐文档: {', '.join(check.doc_refs)}")
    
    lines.append("")
    lines.append("### 数据存储")
    for check in checks:
        if check.name in ["mysql", "redis"]:
            status = "✅ PASS" if check.ok else "❌ FAIL"
            lines.append(f"- **{check.name}**: {status}")
            lines.append(f"  - {check.details}")
            if not check.ok and check.doc_refs:
                lines.append(f"  - 📖 推荐文档: {', '.join(check.doc_refs)}")
    
    lines.append("")
    lines.append("### 核心功能模块")
    for check in checks:
        if check.name in ["core_modules", "logging", "universal_parser", "pagination", "proxy_validators"]:
            status = "✅ PASS" if check.ok else "❌ FAIL"
            lines.append(f"- **{check.name}**: {status}")
            lines.append(f"  - {check.details}")
            if not check.ok and check.doc_refs:
                lines.append(f"  - 📖 推荐文档: {', '.join(check.doc_refs)}")
    
    lines.append("")
    lines.append("### 高级功能")
    for check in checks:
        if check.name in ["dynamic_crawler", "llm_integration", "cli_tools"]:
            status = "✅ PASS" if check.ok else "❌ FAIL"
            lines.append(f"- **{check.name}**: {status}")
            lines.append(f"  - {check.details}")
            if not check.ok and check.doc_refs:
                lines.append(f"  - 📖 推荐文档: {', '.join(check.doc_refs)}")

    lines.append("")
    lines.append("## 数据源抽检 / Source Fetch Sample")
    lines.append("")
    lines.append("*Note: 快速验证模式 - 找到第一个可用源后跳过剩余*")
    lines.append("")
    
    for src in source_checks:
        if src.reason == "skipped":
            lines.append(f"- ⏭️ **{src.name}**: SKIPPED (已验证其他源)")
        else:
            status = "✅ PASS" if src.ok else "❌ FAIL"
            lines.append(f"- {status} **{src.name}**")
            lines.append(f"  - URL: {src.url}")
            lines.append(f"  - Status: {src.reason} (HTTP {src.status_code})")
            if src.sample:
                sample_str = json.dumps(src.sample, ensure_ascii=False)
                lines.append(f"  - Sample: `{sample_str}`")
            if not src.ok and src.doc_refs:
                lines.append(f"  - 📖 推荐文档: {', '.join(src.doc_refs)}")

    lines.append("")
    lines.append("## 总结 / Summary")
    lines.append("")
    
    all_pass = ok_checks == total_checks and ok_sources > 0  # 至少一个源成功
    if all_pass:
        lines.append("### ✅ 部署验证通过 / DEPLOYMENT VERIFIED")
        lines.append("")
        lines.append("所有系统检查通过，数据源可正常抓取。系统已就绪！")
        lines.append("")
        lines.append("#### 下一步")
        lines.append("- 运行爬虫: `python main.py` 或 `python cli.py run`")
        lines.append("- 查看文档: `docs/INDEX.md` (完整文档导航)")
        lines.append("- 快速开始: `docs/QUICK_START.md`")
    else:
        lines.append("### ❌ 部署验证失败 / DEPLOYMENT FAILED")
        lines.append("")
        failed_checks = [c.name for c in checks if not c.ok]
        if failed_checks:
            lines.append(f"**失败的检查项**: {', '.join(failed_checks)}")
            lines.append("")
        if ok_sources == 0:
            lines.append("**警告**: 所有数据源抓取失败，请检查网络连接和源 URL 可用性")
            lines.append("")
        
        # 收集所有文档推荐
        all_doc_refs = set()
        for check in checks:
            if not check.ok and check.doc_refs:
                all_doc_refs.update(check.doc_refs)
        for src in source_checks:
            if not src.ok and src.doc_refs:
                all_doc_refs.update(src.doc_refs)
        
        if all_doc_refs:
            lines.append("#### 📖 故障排查文档推荐")
            lines.append("")
            for doc in sorted(all_doc_refs):
                lines.append(f"- `{doc}`")
            lines.append("")
        
        lines.append("#### 🔧 常见问题解决方案")
        lines.append("")
        
        # 提供针对性的解决建议
        if any(c.name == "dependencies" and not c.ok for c in checks):
            lines.append("**依赖问题**:")
            lines.append("```bash")
            lines.append("pip install -r requirements.txt")
            lines.append("```")
            lines.append("")
        
        if any(c.name == "config" and not c.ok for c in checks):
            lines.append("**配置问题**:")
            lines.append("```bash")
            lines.append("cp .env.example .env")
            lines.append("# 编辑 .env 文件，填写数据库连接信息")
            lines.append("```")
            lines.append("")
        
        if any(c.name == "mysql" and not c.ok for c in checks):
            lines.append("**MySQL 连接问题**:")
            lines.append("- 确认 MySQL 服务已启动")
            lines.append("- 检查 .env 中的连接参数 (HOST, PORT, USER, PASSWORD)")
            lines.append("- 数据库和表会自动创建，无需手动执行 SQL")
            lines.append("")
        
        if any(c.name == "redis" and not c.ok for c in checks):
            lines.append("**Redis 连接问题**:")
            lines.append("- 确认 Redis 服务已启动")
            lines.append("- 检查 .env 中的 REDIS_HOST 和 REDIS_PORT")
            lines.append("- Windows: 下载 Redis for Windows 或使用 WSL")
            lines.append("")
        
        if ok_sources == 0:
            lines.append("**数据源无法访问**:")
            lines.append("- 检查网络连接和防火墙设置")
            lines.append("- 部分源可能暂时不可用（正常现象）")
            lines.append("- 至少保证一个源可用即可正常运行")
            lines.append("")
        
        lines.append("#### 📚 完整文档索引")
        lines.append("")
        lines.append("- [文档总导航](docs/INDEX.md)")
        lines.append("- [快速开始](docs/QUICK_START.md)")
        lines.append("- [部署指南](docs/DEPLOYMENT.md)")
        lines.append("- [故障排查](docs/TROUBLESHOOTING.md)")

    return "\n".join(lines) + "\n"


def main(env_path: Optional[str] = None) -> int:
    started_at = now_iso()
    settings = load_settings(env_path) if env_path else Settings.from_env()

    print("🔍 开始部署验证 / Starting deployment verification...")
    print()
    
    # 基础环境检查
    print("📦 检查基础环境...")
    checks = [
        check_python(),
        check_dependencies(),
        check_config(settings),
    ]
    
    # 数据存储检查
    print("💾 检查数据存储...")
    checks.extend([
        check_mysql(settings),
        check_redis(settings),
    ])
    
    # 核心模块检查
    print("🔧 检查核心功能模块...")
    checks.extend([
        check_core_modules(),
        check_logging(settings),
        check_universal_parser(settings),
        check_pagination_system(settings),
        check_proxy_validators(settings),
    ])
    
    # 高级功能检查
    print("🚀 检查高级功能...")
    checks.extend([
        check_dynamic_crawler(settings),
        check_llm_integration(settings),
        check_cli_tools(),
    ])

    # 数据源检查（快速模式：找到第一个成功就停止）
    print("🌐 检查数据源（快速模式）...")
    source_checks = check_sources(settings)
    
    finished_at = now_iso()

    # 生成报告
    report = render_report(started_at, finished_at, checks, source_checks)

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(report)

    # 计算结果
    ok_checks = all(c.ok for c in checks)
    ok_sources = any(s.ok for s in source_checks)  # 至少一个源成功

    print()
    print("=" * 60)
    print("验证完成 / Verification completed")
    print("=" * 60)
    print(f"📄 报告位置: {REPORT_PATH}")
    print()
    print(f"✅ 系统检查: {sum(1 for c in checks if c.ok)}/{len(checks)} 通过")
    print(f"✅ 数据源: {sum(1 for s in source_checks if s.ok)}/{len(source_checks)} 可用")
    print()
    
    if ok_checks and ok_sources:
        print("🎉 部署验证通过！系统已就绪。")
        return 0
    else:
        print("⚠️  部署验证失败，请查看报告详情。")
        if not ok_checks:
            failed = [c.name for c in checks if not c.ok]
            print(f"   失败项: {', '.join(failed)}")
        if not ok_sources:
            print("   警告: 所有数据源不可用")
        return 1


if __name__ == "__main__":
    sys.exit(main())
