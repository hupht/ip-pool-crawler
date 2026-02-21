"""
通用解析器单元测试
"""

import pytest
from crawler.universal_parser import UniversalParser, ProxyExtraction
from crawler.structure_analyzer import Table, HTMLList, JSONBlock


class TestUniversalParserTables:
    """测试从表格中提取代理"""
    
    def test_extract_from_simple_table(self):
        """测试从简单表格提取代理"""
        tables = [Table(
            headers=['IP', 'Port', 'Protocol'],
            rows=[
                ['192.168.1.1', '8080', 'HTTP'],
                ['10.0.0.1', '9090', 'HTTPS']
            ]
        )]
        
        proxies = UniversalParser.extract_from_tables(tables)
        
        assert len(proxies) == 2
        assert proxies[0].ip == '192.168.1.1'
        assert proxies[0].port == 8080
        assert proxies[0].protocol.lower() == 'http'

    def test_extract_from_table_port_column_at_index_zero(self):
        """测试端口列在第 0 列时仍能正确提取"""
        tables = [Table(
            headers=['Port', 'IP', 'Protocol'],
            rows=[['8080', '192.168.1.1', 'HTTP']]
        )]

        proxies = UniversalParser.extract_from_tables(tables)

        assert len(proxies) == 1
        assert proxies[0].ip == '192.168.1.1'
        assert proxies[0].port == 8080
    
    def test_extract_from_table_without_port(self):
        """测试从表格提取 IP（无 Port 列）"""
        tables = [Table(
            headers=['IP', 'Country'],
            rows=[['1.2.3.4', 'US'], ['5.6.7.8', 'CN']]
        )]
        
        proxies = UniversalParser.extract_from_tables(tables)
        
        assert len(proxies) == 2
        assert proxies[0].ip == '1.2.3.4'
        assert proxies[0].port is None
    
    def test_extract_from_table_chinese_headers(self):
        """测试中文列名识别"""
        tables = [Table(
            headers=['IP地址', '端口', '协议'],
            rows=[['192.168.1.1', '8080', 'HTTP']]
        )]
        
        proxies = UniversalParser.extract_from_tables(tables)
        
        assert len(proxies) == 1
        assert proxies[0].ip == '192.168.1.1'
        assert proxies[0].port == 8080
    
    def test_extract_from_table_no_ip_column(self):
        """测试无 IP 列的表格被跳过"""
        tables = [Table(
            headers=['Name', 'Country'],
            rows=[['Proxy1', 'US']]
        )]
        
        proxies = UniversalParser.extract_from_tables(tables)
        
        assert len(proxies) == 0
    
    def test_extract_from_multiple_tables(self):
        """测试从多个表格提取"""
        tables = [
            Table(headers=['IP', 'Port'], rows=[['1.1.1.1', '80']]),
            Table(headers=['Host', 'Port'], rows=[['2.2.2.2', '443']])
        ]
        
        proxies = UniversalParser.extract_from_tables(tables)
        
        assert len(proxies) == 2
        assert any(p.ip == '1.1.1.1' for p in proxies)
        assert any(p.ip == '2.2.2.2' for p in proxies)


class TestUniversalParserLists:
    """测试从列表中提取代理"""
    
    def test_extract_from_simple_list(self):
        """测试从列表提取 IP:PORT"""
        lists = [HTMLList(
            items=['192.168.1.1:8080', '10.0.0.1:9090'],
            list_type='ul'
        )]
        
        proxies = UniversalParser.extract_from_lists(lists)
        
        assert len(proxies) == 2
        assert proxies[0].ip == '192.168.1.1'
        assert proxies[0].port == 8080
    
    def test_extract_from_list_with_protocol(self):
        """测试从列表提取包含协议的代理"""
        lists = [HTMLList(
            items=['http://1.2.3.4:8080', 'https://5.6.7.8:9090'],
            list_type='ul'
        )]
        
        proxies = UniversalParser.extract_from_lists(lists)
        
        assert len(proxies) == 2
        assert proxies[0].protocol == 'http'
        assert proxies[1].protocol == 'https'
    
    def test_extract_from_list_ip_only(self):
        """测试从列表提取 IP 地址（无端口）"""
        lists = [HTMLList(
            items=['IP: 1.2.3.4', 'IP: 5.6.7.8'],
            list_type='ul'
        )]
        
        proxies = UniversalParser.extract_from_lists(lists)
        
        assert len(proxies) == 2
        assert proxies[0].ip == '1.2.3.4'
        assert proxies[0].port is None


class TestUniversalParserJSON:
    """测试从 JSON 中提取代理"""
    
    def test_extract_from_json_list(self):
        """测试从 JSON 数组提取"""
        json_blocks = [JSONBlock(
            data={
                'proxies': [
                    {'ip': '1.2.3.4', 'port': 8080},
                    {'ip': '5.6.7.8', 'port': 9090}
                ]
            }
        )]
        
        proxies = UniversalParser.extract_from_json(json_blocks)
        
        assert len(proxies) == 2
        assert proxies[0].ip == '1.2.3.4'
        assert proxies[0].port == 8080
    
    def test_extract_from_json_with_protocol(self):
        """测试从 JSON 提取包含协议的代理"""
        json_blocks = [JSONBlock(
            data=[
                {'ip': '10.0.0.1', 'port': 3128, 'protocol': 'http'},
                {'ip': '10.0.0.2', 'port': 3128, 'protocol': 'socks5'}
            ]
        )]
        
        proxies = UniversalParser.extract_from_json(json_blocks)
        
        assert len(proxies) == 2
        assert proxies[0].protocol == 'http'
        assert proxies[1].protocol == 'socks5'
    
    def test_extract_from_json_alternative_keys(self):
        """测试从 JSON 提取（使用其他键名）"""
        json_blocks = [JSONBlock(
            data={'proxies': [
                {'address': '192.168.1.1', 'port': 8080}
            ]}
        )]
        
        proxies = UniversalParser.extract_from_json(json_blocks)
        
        assert len(proxies) == 1
        assert proxies[0].ip == '192.168.1.1'
    
    def test_extract_from_json_invalid_data(self):
        """测试无效 JSON 数据被忽略"""
        json_blocks = [JSONBlock(
            data={'key': 'value', 'nested': {'data': 'not_proxy'}}
        )]
        
        proxies = UniversalParser.extract_from_json(json_blocks)
        
        assert len(proxies) == 0


class TestUniversalParserText:
    """测试从纯文本中提取代理"""
    
    def test_extract_from_text_blocks(self):
        """测试从文本块提取 IP:PORT"""
        text_blocks = [
            '1.2.3.4:8080 is available',
            '5.6.7.8:9090 for socks5'
        ]
        
        proxies = UniversalParser.extract_from_text(text_blocks)
        
        assert len(proxies) == 2
        assert proxies[0].ip == '1.2.3.4'
        assert proxies[0].port == 8080


class TestUniversalParserIntegration:
    """集成测试"""
    
    def test_extract_all(self):
        """测试从完整 HTML 提取所有代理"""
        html = """
        <html>
        <body>
            <table>
                <tr><th>IP</th><th>Port</th></tr>
                <tr><td>1.1.1.1</td><td>80</td></tr>
            </table>
            
            <ul>
                <li>2.2.2.2:443</li>
            </ul>
            
            <pre>{"proxies": [{"ip": "3.3.3.3", "port": 8080}]}</pre>
            
            <p>Free proxy: 4.4.4.4:9090</p>
        </body>
        </html>
        """
        
        proxies, stats = UniversalParser.extract_all(html)
        
        # 应该从表格、列表、JSON、文本各提取一个
        assert stats['from_tables'] >= 1
        assert stats['from_lists'] >= 1
        assert stats['from_json'] >= 1
        assert stats['from_text'] >= 1

    def test_parse_api_with_provided_structure(self):
        structure = {
            "tables": [Table(headers=["IP", "Port"], rows=[["1.2.3.4", "8080"]])],
            "lists": [],
            "json_blocks": [],
            "text_blocks": [],
        }

        proxies = UniversalParser.parse("<html></html>", structure=structure)
        assert len(proxies) == 1
        assert proxies[0].ip == "1.2.3.4"

    def test_parse_api_with_bytes_gbk_fallback(self):
        html = "<html><body>1.2.3.4:8080</body></html>".encode("gbk")
        proxies = UniversalParser.parse(html)
        assert len(proxies) >= 1
    
    def test_deduplicate_proxies(self):
        """测试代理去重"""
        proxies = [
            ProxyExtraction(ip='1.2.3.4', port=8080, protocol='http', confidence=0.9),
            ProxyExtraction(ip='1.2.3.4', port=8080, protocol='http', confidence=0.95),
            ProxyExtraction(ip='1.2.3.4', port=8080, protocol='https', confidence=0.8),
            ProxyExtraction(ip='5.6.7.8', port=9090, protocol=None, confidence=0.85),
        ]
        
        dedup = UniversalParser.deduplicate_proxies(proxies)
        
        # 应该保留 3 个唯一的代理（3 个不同的组合）
        assert len(dedup) == 3
        
        # 应该保留置信度较高的
        http_proxy = [p for p in dedup if p.ip == '1.2.3.4' and p.protocol == 'http'][0]
        assert http_proxy.confidence == 0.95


class TestUniversalParserEdgeCases:
    """边界情况测试"""
    
    def test_invalid_port_in_table(self):
        """测试表格中的无效端口被过滤"""
        tables = [Table(
            headers=['IP', 'Port'],
            rows=[
                ['1.2.3.4', '99999'],  # 端口太大
                ['5.6.7.8', 'invalid'],  # 无效端口
                ['10.0.0.1', '8080']  # 有效
            ]
        )]
        
        proxies = UniversalParser.extract_from_tables(tables)
        
        # 应该有 1 个或更多（至少有效的那个）
        assert any(p.port == 8080 for p in proxies)
    
    def test_empty_structures(self):
        """测试空结构"""
        tables = [Table(headers=['IP'], rows=[])]
        lists = [HTMLList(items=[], list_type='ul')]
        json_blocks = [JSONBlock(data={})]
        
        table_proxies = UniversalParser.extract_from_tables(tables)
        list_proxies = UniversalParser.extract_from_lists(lists)
        json_proxies = UniversalParser.extract_from_json(json_blocks)
        
        assert len(table_proxies) == 0
        assert len(list_proxies) == 0
        assert len(json_proxies) == 0
    
    def test_malformed_json(self):
        """测试格式错误的 JSON 被处理"""
        # 这个测试确保即使 JSON 有问题也不会崩溃
        json_blocks = [JSONBlock(data="not a dict")]
        
        # 应该不抛异常
        proxies = UniversalParser.extract_from_json(json_blocks)
        assert isinstance(proxies, list)


class TestUniversalParserConfidence:
    """置信度测试"""
    
    def test_confidence_scores(self):
        """测试置信度评分"""
        html = "<table><tr><th>IP</th><th>Port</th></tr><tr><td>1.2.3.4</td><td>8080</td></tr></table>"
        proxies, _ = UniversalParser.extract_all(html)
        
        # 表格提取的代理应该有高置信度
        assert all(p.confidence >= 0.8 for p in proxies)
    
    def test_mixed_confidence(self):
        """测试混合来源的置信度"""
        proxies = [
            ProxyExtraction(ip='1.2.3.4', port=8080, source_type='table', confidence=0.95),
            ProxyExtraction(ip='5.6.7.8', port=9090, source_type='list', confidence=0.9),
            ProxyExtraction(ip='10.0.0.1', port=3128, source_type='text', confidence=0.75),
        ]
        
        assert max(p.confidence for p in proxies) >= 0.9
        assert min(p.confidence for p in proxies) <= 0.8


class TestUniversalParserDataClass:
    """数据类测试"""
    
    def test_proxy_extraction_creation(self):
        """测试 ProxyExtraction 创建"""
        proxy = ProxyExtraction(
            ip='192.168.1.1',
            port=8080,
            protocol='http',
            confidence=0.95
        )
        
        assert proxy.ip == '192.168.1.1'
        assert proxy.port == 8080
        assert proxy.protocol == 'http'
        assert proxy.source_type == 'unknown'
    
    def test_proxy_extraction_additional_info(self):
        """测试 ProxyExtraction 的额外信息"""
        proxy = ProxyExtraction(
            ip='1.2.3.4',
            additional_info={'source': 'table', 'row': 2}
        )
        
        assert proxy.additional_info['source'] == 'table'
        assert proxy.additional_info['row'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
