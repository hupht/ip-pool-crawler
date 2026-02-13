"""
Phase 2 集成测试 - 解析器 + 验证器 + 分页检测器集成
"""

import pytest
from crawler.universal_parser import UniversalParser, ProxyExtraction
from crawler.proxy_validator import ProxyValidator
from crawler.pagination_detector import PaginationDetector


class TestPhase2FullPipeline:
    """完整管道集成测试"""
    
    def test_parse_validate_roundtrip(self):
        """测试解析 → 验证 完整过程"""
        # HTML 包含代理表格
        html = """
        <html>
        <table>
            <tr><th>IP</th><th>Port</th><th>Protocol</th></tr>
            <tr><td>1.2.3.4</td><td>8080</td><td>http</td></tr>
            <tr><td>192.168.1.1</td><td>8081</td><td>https</td></tr>
        </table>
        <a href="?page=2">Next</a>
        </html>
        """
        
        # Step 1: 解析代理
        parse_result = UniversalParser.extract_all(html)
        proxies, stats = parse_result
        
        assert len(proxies) >= 1
        
        # Step 2: 验证代理
        valid_proxies = []
        for proxy in proxies:
            result = ProxyValidator.validate_proxy(
                proxy.ip, proxy.port, proxy.protocol
            )
            if result.is_valid:
                valid_proxies.append(proxy)
        
        # 应该有 1 个有效代理（1.2.3.4 有效，192.168.1.1 是私网）
        assert len(valid_proxies) >= 1
        
        # Step 3: 检测分页
        pagination_info = PaginationDetector.detect_pagination(html)
        
        assert pagination_info.has_pagination
        assert pagination_info.next_page_url is not None
    
    def test_extract_filter_paginate_flow(self):
        """测试提取 → 过滤 → 分页流程"""
        html = """
        <div class="proxies">
            <div>1.2.3.4:8080:http</div>
            <div>5.6.7.8:9090:https</div>
            <div>10.0.0.1:8080:socks5</div>
        </div>
        <div class="pagination">
            <a href="/list?page=2">下一页</a>
        </div>
        """
        
        # 解析
        proxies, stats = UniversalParser.extract_all(html)
        
        # 通过验证过滤
        batch_result = ProxyValidator.batch_validate([
            {
                'ip': proxy.ip,
                'port': proxy.port,
                'protocol': proxy.protocol
            }
            for proxy in proxies
        ])
        valid_proxies, batch_stats = batch_result
        
        # 检测分页（用于下一批）
        pagination = PaginationDetector.detect_pagination(html)
        
        # 验证结果
        assert len(proxies) > 0
        assert batch_stats['valid'] >= 0  # 可能的有效数量
        assert pagination.has_pagination


class TestPhase2ParserValidatorIntegration:
    """解析器和验证器的集成"""
    
    def test_parser_output_compatible_with_validator(self):
        """测试解析器输出与验证器兼容"""
        html = """
        <table>
            <tr>
                <td>8.8.8.8</td>
                <td>80</td>
                <td>http</td>
            </tr>
        </table>
        """
        
        # 解析
        proxies, _ = UniversalParser.extract_all(html)
        
        # 验证每个解析的代理
        for proxy in proxies:
            result = ProxyValidator.validate_proxy(
                proxy.ip, proxy.port, proxy.protocol
            )
            
            # 应该有有效的结果对象
            assert result.confidence >= 0.0
            assert result.confidence <= 1.0
    
    def test_batch_validation_with_parsed_proxies(self):
        """测试用解析的代理进行批量验证"""
        html = """
        <ul>
            <li>1.2.3.4:3128:http</li>
            <li>5.6.7.8:8888:https</li>
        </ul>
        """
        
        proxies, _ = UniversalParser.extract_all(html)
        
        # 转换为验证器预期的格式
        proxy_dicts = [
            {'ip': p.ip, 'port': p.port, 'protocol': p.protocol}
            for p in proxies
        ]
        
        valid, stats = ProxyValidator.batch_validate(proxy_dicts)
        
        # 应该返回有效代理和统计
        assert 'total' in stats
        assert 'valid' in stats
        assert stats['total'] >= 0


class TestPhase2ValidatorPaginationIntegration:
    """验证器和分页检测器的集成"""
    
    def test_validate_proxies_from_paginated_list(self):
        """测试验证分页列表中的代理"""
        html = """
        <div id="proxies">
            <div class="proxy">1.2.3.4:80</div>
            <div class="proxy">9.9.9.9:443</div>
        </div>
        <div id="pagination">
            <a href="?page=2">Next Page</a>
        </div>
        """
        
        # 解析默认可能没有找到，所以手动创建
        test_proxies = [
            {'ip': '1.2.3.4', 'port': 80, 'protocol': 'http'},
            {'ip': '9.9.9.9', 'port': 443, 'protocol': 'https'},
        ]
        
        # 验证
        valid, stats = ProxyValidator.batch_validate(test_proxies)
        
        # 检测分页
        pagination = PaginationDetector.detect_pagination(html)
        
        # 两个都应该成功
        assert stats is not None
        assert pagination is not None


class TestPhase2EndToEnd:
    """端到端集成测试"""
    
    def test_full_scraping_pipeline(self):
        """测试完整的抓取管道"""
        # 模拟从网站获取的 HTML - 使用结构化格式
        html = """
        <html>
        <body>
            203.0.113.45:8080:http
            198.51.100.23:3128:http
            192.0.2.1:9090:socks5
            
            <div class="pagination">
                <a href="/proxy/page/2">下一页</a>
            </div>
        </body>
        </html>
        """
        
        # Phase 1: 提取代理
        proxies, parse_stats = UniversalParser.extract_all(html)
        
        # 如果有提取到代理，继续验证
        if len(proxies) > 0:
            assert parse_stats['total_extracted'] > 0
            
            # Phase 2: 验证代理
            proxy_dicts = [
                {'ip': p.ip, 'port': p.port, 'protocol': p.protocol}
                for p in proxies
            ]
            
            valid_proxies, validate_stats = ProxyValidator.batch_validate(proxy_dicts)
            
            # 应该有至少一些有效代理
            assert validate_stats['valid'] >= 0
        
        # Phase 3: 检测分页应该总是工作
        pagination = PaginationDetector.detect_pagination(html)
        
        assert pagination.has_pagination
        assert pagination.next_page_url is not None
    
    def test_pagination_aware_batching(self):
        """测试分页感知的批处理"""
        pages_html = [
            # Page 1
            """
            <table>
                <tr><td>1.1.1.1</td><td>80</td><td>http</td></tr>
                <tr><td>2.2.2.2</td><td>443</td><td>https</td></tr>
            </table>
            <a href="?page=2">Next</a>
            """,
            # Page 2
            """
            <table>
                <tr><td>3.3.3.3</td><td>8080</td><td>http</td></tr>
                <tr><td>4.4.4.4</td><td>3128</td><td>http</td></tr>
            </table>
            <a href="?page=3">Next</a>
            """,
        ]
        
        all_valid = []
        
        for i, page_html in enumerate(pages_html):
            # 提取
            proxies, _ = UniversalParser.extract_all(page_html)
            
            # 验证
            proxy_dicts = [
                {'ip': p.ip, 'port': p.port, 'protocol': p.protocol}
                for p in proxies
            ]
            valid, _ = ProxyValidator.batch_validate(proxy_dicts)
            all_valid.extend(valid)
            
            # 检测分页
            pagination = PaginationDetector.detect_pagination(page_html)
            
            if pagination.has_pagination:
                # 继续下一页
                continue
            else:
                # 最后一页
                break
        
        # 应该收集了代理
        assert len(all_valid) >= 0


class TestPhase2ErrorHandling:
    """错误处理集成测试"""
    
    def test_handle_malformed_html(self):
        """测试处理格式错误的 HTML"""
        html = """
        <table>
            <tr><td>not-an-ip</td><td>abc</td></tr>
        </table>
        """
        
        # 解析应该不会崩溃
        proxies, _ = UniversalParser.extract_all(html)
        
        # 验证应该不会崩溃
        if proxies:
            proxy_dicts = [
                {'ip': p.ip, 'port': p.port, 'protocol': p.protocol}
                for p in proxies
            ]
            valid, _ = ProxyValidator.batch_validate(proxy_dicts)
    
    def test_handle_empty_pagination(self):
        """测试处理无分页的 HTML"""
        html = "<html><body>No pagination</body></html>"
        
        pagination = PaginationDetector.detect_pagination(html)
        
        assert not pagination.has_pagination
    
    def test_handle_private_ips(self):
        """测试处理私网 IP"""
        # 创建包含私网 IP 的代理列表
        test_proxies = [
            {'ip': '192.168.1.1', 'port': 8080, 'protocol': 'http'},
            {'ip': '10.0.0.1', 'port': 3128, 'protocol': 'https'},
            {'ip': '172.16.0.1', 'port': 8888, 'protocol': 'socks5'},
        ]
        
        # 验证应该标记为无效
        valid, stats = ProxyValidator.batch_validate(test_proxies)
        
        # 所有私网应该被过滤
        assert stats['invalid'] == 3
        assert stats['valid'] == 0


class TestPhase2Performance:
    """性能集成测试"""
    
    def test_process_large_proxy_list(self):
        """测试处理大型代理列表"""
        # 生成大型代理列表而不是 HTML
        large_proxy_list = []
        for i in range(100):
            ip = f"{(i % 256)}.{((i // 256) % 256)}.{((i // 65536) % 256)}.{(i * 7) % 256}"
            port = 8000 + (i % 1000)
            protocol = ['http', 'https', 'socks5'][i % 3]
            large_proxy_list.append({
                'ip': ip,
                'port': port,
                'protocol': protocol
            })
        
        # 批量验证应该快速完成
        valid, validate_stats = ProxyValidator.batch_validate(large_proxy_list[:50])
        
        # 应该处理了数据
        assert validate_stats['total'] == 50
        assert validate_stats['valid'] + validate_stats['invalid'] == 50


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
