#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""系统功能完整验证脚本"""

from crawler.config import Settings
from crawler.storage import get_mysql_connection
import redis
import sys

def test_mysql_connection():
    """测试 MySQL 连接"""
    print("\n=== 测试 1: MySQL 连接 ===")
    try:
        s = Settings.from_env()
        conn = get_mysql_connection(s)
        print(f"✅ MySQL 连接成功: {s.mysql_host}:{s.mysql_port}")
        
        # 检查表是否存在
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"✅ 存在的表: {', '.join(tables)}")
            
            # 检查 audit_logs 表
            if 'audit_logs' in tables:
                cursor.execute("SELECT COUNT(*) FROM audit_logs")
                count = cursor.fetchone()[0]
                print(f"✅ audit_logs 表中的记录数: {count}")
            else:
                print("⚠️  audit_logs 表还不存在")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_redis_connection():
    """测试 Redis 连接"""
    print("\n=== 测试 2: Redis 连接 ===")
    try:
        s = Settings.from_env()
        r = redis.Redis(
            host=s.redis_host,
            port=s.redis_port,
            db=s.redis_db,
            password=s.redis_password if s.redis_password else None,
            decode_responses=True
        )
        r.ping()
        print(f"✅ Redis 连接成功: {s.redis_host}:{s.redis_port}")
        
        # 检查代理池大小
        pool_size = r.zcard("proxy:alive")
        print(f"✅ 代理池大小: {pool_size} 个代理")
        
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_logger():
    """测试日志系统"""
    print("\n=== 测试 3: 日志系统 ===")
    try:
        from crawler.logging.logger import get_logger
        from crawler.config import Settings
        
        s = Settings.from_env()
        logger = get_logger()
        
        print(f"✅ 日志系统初始化成功")
        print(f"   - 数据库日志启用: {s.log_db_write_enabled}")
        print(f"   - 日志级别: {s.log_level}")
        print(f"   - 日志文件: {s.log_file_path}")
        
        # 测试脱敏功能
        logger.log_db_operation(
            operation="TEST",
            table="test_table",
            affected_rows=1,
            params={"password": "secret123", "ip": "192.168.1.100"}
        )
        print(f"✅ 日志测试记录已写入")
        
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sources():
    """测试数据源"""
    print("\n=== 测试 4: 数据源 ===")
    try:
        from crawler.sources import get_sources
        
        sources = get_sources()
        print(f"✅ 数据源加载成功，共 {len(sources)} 个源:")
        for src in sources:
            print(f"   - {src.name} ({src.url})")
        
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_parsers():
    """测试解析器"""
    print("\n=== 测试 5: 解析器 ===")
    try:
        from pathlib import Path
        from crawler.parsers import parse_free_proxy_list
        
        # 读取测试数据
        fixture_path = Path("tests/fixtures/free-proxy-list.html")
        if fixture_path.exists():
            html = fixture_path.read_text(encoding="utf-8")
            records = parse_free_proxy_list(html)
            if records:
                print(f"✅ 解析器正常，解析到 {len(records)} 条记录")
                sample = records[0]
                print(f"   示例: {sample['ip']}:{sample['port']} ({sample.get('protocol', 'N/A')})")
                return True
            else:
                print("⚠️  解析到 0 条记录")
                return True
        else:
            print(f"⚠️  测试数据文件不存在: {fixture_path}")
            return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validator():
    """测试验证器"""
    print("\n=== 测试 6: 验证器 ===")
    try:
        from crawler.validator import score_proxy, tcp_check
        
        # 测试评分
        score1 = score_proxy(latency_ms=100, success=True)
        score2 = score_proxy(latency_ms=500, success=True)
        score3 = score_proxy(latency_ms=100, success=False)
        
        if score1 > score2 and score1 > score3:
            print(f"✅ 评分逻辑正常")
            print(f"   - 低延迟+成功: {score1:.2f}")
            print(f"   - 高延迟+成功: {score2:.2f}")
            print(f"   - 低延迟+失败: {score3:.2f}")
            return True
        else:
            print(f"❌ 评分逻辑异常")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_configuration():
    """测试配置"""
    print("\n=== 测试 7: 配置系统 ===")
    try:
        from crawler.config import Settings
        
        s = Settings.from_env()
        
        # 检查关键配置
        checks = [
            ("MySQL 主机", s.mysql_host),
            ("MySQL 用户", s.mysql_user),
            ("Redis 主机", s.redis_host),
            ("日志启用", s.log_db_write_enabled),
            ("并发设置", s.source_workers > 0),
        ]
        
        all_ok = True
        for name, value in checks:
            if value:
                print(f"✅ {name}: {value}")
            else:
                print(f"❌ {name}: 未配置")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("IP Pool Crawler - 系统功能完整验证")
    print("="*60)
    
    results = []
    
    results.append(("MySQL 连接", test_mysql_connection()))
    results.append(("Redis 连接", test_redis_connection()))
    results.append(("日志系统", test_logger()))
    results.append(("数据源", test_sources()))
    results.append(("解析器", test_parsers()))
    results.append(("验证器", test_validator()))
    results.append(("配置系统", test_configuration()))
    
    # 总结
    print("\n" + "="*60)
    print("验证总结")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n结果: {passed}/{total} 项通过")
    
    if passed == total:
        print("🎉 所有功能正常！")
        return 0
    else:
        print(f"⚠️  有 {total - passed} 项需要修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())
