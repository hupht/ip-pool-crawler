"""
通用检测器测试
"""

import pytest
from crawler.universal_detector import UniversalDetector, MatchType, IPMatch


class TestUniversalDetector:
    """通用检测器单元测试"""
    
    def test_detect_ip_port_pairs_basic(self):
        """测试基本的 IP:PORT 检测"""
        html = "Proxy: 1.2.3.4:8080"
        results = UniversalDetector.detect_ip_port_pairs(html)
        
        assert len(results) == 1
        assert results[0].ip == "1.2.3.4"
        assert results[0].port == 8080
        assert results[0].confidence == 0.95
    
    def test_detect_ip_port_pairs_multiple(self):
        """测试多个 IP:PORT 检测"""
        html = """
        1.2.3.4:8080
        5.6.7.8:9090
        10.11.12.13:443
        """
        results = UniversalDetector.detect_ip_port_pairs(html)
        
        assert len(results) == 3
        assert results[0].port == 8080
        assert results[1].port == 9090
        assert results[2].port == 443
    
    def test_detect_invalid_ports(self):
        """测试无效端口过滤"""
        html = """
        1.2.3.4:0
        5.6.7.8:65536
        10.11.12.13:70000
        """
        results = UniversalDetector.detect_ip_port_pairs(html)
        
        # 所有端口都应该被过滤掉
        assert len(results) == 0
    

    def test_detect_ips_independent(self):
        """测试独立 IP 检测"""
        html = """
        IP: 1.2.3.4 is down
        Try 5.6.7.8 instead
        """
        results = UniversalDetector.detect_ips(html)
        
        assert len(results) >= 2
        ips = [r.ip for r in results]
        assert "1.2.3.4" in ips
        assert "5.6.7.8" in ips
    
    def test_detect_ips_with_port_context(self):
        """测试在上下文中找到端口"""
        html = "<td>1.2.3.4</td> <td>8080</td>"
        results = UniversalDetector.detect_ips(html)
        
        # 应该检测到 IP，并尝试从上下文找端口
        assert len(results) >= 1
        # 由于上下文中有端口，置信度应该更高
        ip_match = [r for r in results if r.ip == "1.2.3.4"][0]
        assert ip_match.confidence >= 0.6
    
    def test_detect_protocols(self):
        """测试协议检测"""
        html = """
        protocol: http
        Protocol: HTTPS
        Type: socks5
        """
        results = UniversalDetector.detect_protocols(html)
        
        assert len(results) >= 1
        protocols = results
        assert 'http' in protocols or 'https' in protocols or 'socks5' in protocols

    def test_detect_ports(self):
        """测试端口检测"""
        html = """
        1.2.3.4:8080
        port = 9090
        5.6.7.8:8080
        """
        results = UniversalDetector.detect_ports(html)

        assert 8080 in results
        assert 9090 in results
        assert results.count(8080) == 1

        def test_extract_protocol_prefers_https_over_http(self):
            protocol = UniversalDetector._extract_protocol_from_context("proxy=https://5.6.7.8:9090")
            assert protocol == "https"
    
    def test_validate_ip(self):
        """测试 IP 验证"""
        assert UniversalDetector._validate_ip("1.2.3.4") == True
        assert UniversalDetector._validate_ip("192.168.1.1") == True
        assert UniversalDetector._validate_ip("255.255.255.255") == True
        assert UniversalDetector._validate_ip("256.1.1.1") == False
        assert UniversalDetector._validate_ip("1.1.1") == False
        assert UniversalDetector._validate_ip("invalid") == False
    
    def test_validate_port(self):
        """测试端口验证"""
        assert UniversalDetector._validate_port(1) == True
        assert UniversalDetector._validate_port(8080) == True
        assert UniversalDetector._validate_port(65535) == True
        assert UniversalDetector._validate_port(0) == False
        assert UniversalDetector._validate_port(65536) == False
    
    def test_extract_port_from_context(self):
        """测试从上下文提取端口"""
        port = UniversalDetector._extract_port_from_context("IP 1.2.3.4:8080 proxy")
        assert port == 8080
        
        port = UniversalDetector._extract_port_from_context("port = 9090")
        assert port == 9090
        
        port = UniversalDetector._extract_port_from_context("port:443 https")
        assert port == 443
    
    def test_extract_protocol_from_context(self):
        """测试从上下文提取协议"""
        # 直接包含协议文本会被检测到
        protocol = UniversalDetector._extract_protocol_from_context("1.2.3.4:8080 http protocol")
        assert protocol in ["http", "proxy"]  # proxy 也可能被检测到
        
        protocol = UniversalDetector._extract_protocol_from_context("SOCKS5 protocol 1.2.3.4")
        assert protocol == "socks5"
    
    def test_detect_all(self):
        """测试全功能检测"""
        html = """
        <table>
            <tr><td>IP</td><td>Port</td><td>Protocol</td></tr>
            <tr><td>1.2.3.4</td><td>8080</td><td>http</td></tr>
            <tr><td>5.6.7.8:9090</td><td></td><td>https</td></tr>
        </table>
        """
        results = UniversalDetector.detect_all(html)
        
        assert 'ip_port_pairs' in results
        assert 'ips' in results
        assert 'protocols' in results
        
        # 应该检测到 IP:PORT 对
        assert len(results['ip_port_pairs']) >= 1
        # 应该检测到独立 IP
        assert len(results['ips']) >= 1
    
    def test_context_extraction(self):
        """测试上下文提取"""
        html = "前置内容1.2.3.4后置内容"
        results = UniversalDetector.detect_ips(html)
        
        assert len(results) >= 1
        context = results[0].context
        assert "前置" in context
        assert "后置" in context
    
    def test_match_position(self):
        """测试匹配位置"""
        html = "IP is 1.2.3.4:8080 here"
        results = UniversalDetector.detect_ip_port_pairs(html)
        
        assert len(results) == 1
        start, end = results[0].position
        assert html[start:end] == "1.2.3.4:8080"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
