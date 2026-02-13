#!/usr/bin/env python
"""
API 服务器测试客户端示例
演示如何通过 Python 调用 API
"""

import requests
import json

API_BASE = "http://localhost:8000"


def test_health():
    """测试健康检查"""
    print("=" * 60)
    print("测试 1: 健康检查")
    print("=" * 60)
    
    response = requests.get(f"{API_BASE}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def test_crawl_custom():
    """测试爬取自定义 URL"""
    print("=" * 60)
    print("测试 2: 爬取自定义 URL")
    print("=" * 60)
    
    data = {
        "url": "https://www.example.com/proxy-list",
        "max_pages": 1,
        "use_ai": False,
        "no_store": True,  # 不存储，仅测试
        "verbose": True,
    }
    
    print(f"请求数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/crawl-custom",
            json=data,
            timeout=60,
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except requests.exceptions.Timeout:
        print("请求超时")
    except Exception as e:
        print(f"错误: {e}")
    print()


def test_get_proxy():
    """测试获取代理"""
    print("=" * 60)
    print("测试 3: 获取代理")
    print("=" * 60)
    
    params = {
        "count": 5,
        "min_score": 70,
    }
    
    print(f"查询参数: {json.dumps(params, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.get(
            f"{API_BASE}/api/v1/get-proxy",
            params=params,
            timeout=30,
        )
        print(f"状态码: {response.status_code}")
        result = response.json()
        print(f"成功: {result.get('success')}")
        print(f"代理数量: {result.get('count')}")
        
        if result.get('proxies'):
            print("\n代理列表:")
            for i, proxy in enumerate(result['proxies'], 1):
                print(f"  {i}. {proxy['ip']}:{proxy['port']} - "
                      f"{proxy['protocol']} - 分数:{proxy['score']}")
        else:
            print("没有获取到代理")
    except Exception as e:
        print(f"错误: {e}")
    print()


def test_run_crawler():
    """测试运行爬虫（后台任务）"""
    print("=" * 60)
    print("测试 4: 运行爬虫（后台任务）")
    print("=" * 60)
    
    data = {
        "quick_test": True,
        "quick_record_limit": 1,
    }
    
    print(f"请求数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
    print("注意: 这是后台任务，会立即返回")
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/run",
            json=data,
            timeout=10,
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"错误: {e}")
    print()


def test_diagnose_sources():
    """测试诊断源"""
    print("=" * 60)
    print("测试 5: 诊断代理源")
    print("=" * 60)
    
    try:
        response = requests.get(
            f"{API_BASE}/api/v1/diagnose/sources",
            timeout=30,
        )
        print(f"状态码: {response.status_code}")
        result = response.json()
        print(f"成功: {result.get('success')}")
        print(f"\n诊断信息:")
        print(result.get('message', '无信息')[:500] + "...")
    except Exception as e:
        print(f"错误: {e}")
    print()


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("IP 代理池 API 测试客户端")
    print("=" * 60)
    print(f"API 服务器: {API_BASE}")
    print("确保服务器已启动: python cli.py server")
    print()
    
    # 检查服务器是否在线
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code != 200:
            print("❌ 服务器未响应，请先启动服务器")
            return
        print("✓ 服务器在线\n")
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        print("请先启动服务器: python cli.py server")
        return
    
    # 运行测试
    test_health()
    test_get_proxy()
    test_diagnose_sources()
    
    # 以下测试可能需要更长时间或修改数据库，谨慎使用
    # test_crawl_custom()
    # test_run_crawler()
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)
    print("\n访问 http://localhost:8000/docs 查看完整 API 文档")


if __name__ == "__main__":
    main()
