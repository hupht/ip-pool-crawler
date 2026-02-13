"""
代理验证器单元测试
"""

import pytest
from crawler.proxy_validator import ProxyValidator, AnomalyType, ValidationResult


class TestProxyValidatorIP:
    """测试 IP 验证"""
    
    def test_valid_public_ip(self):
        """测试有效的公网 IP"""
        result = ProxyValidator.validate_ip('1.2.3.4')
        assert result.is_valid
        assert result.confidence == 1.0
        assert len(result.anomalies) == 0
    
    def test_invalid_ip_format(self):
        """测试无效的 IP 格式"""
        result = ProxyValidator.validate_ip('999.999.999.999')
        assert not result.is_valid
        assert AnomalyType.INVALID_IP in result.anomalies
    
    def test_empty_ip(self):
        """测试空 IP"""
        result = ProxyValidator.validate_ip('')
        assert not result.is_valid
        assert AnomalyType.INVALID_IP in result.anomalies
    
    def test_private_ip(self):
        """测试私有 IP"""
        result = ProxyValidator.validate_ip('192.168.1.1')
        assert not result.is_valid
        assert AnomalyType.PRIVATE_IP in result.anomalies
        assert result.confidence == 0.2
    
    def test_loopback_ip(self):
        """测试回环 IP"""
        result = ProxyValidator.validate_ip('127.0.0.1')
        assert not result.is_valid
        assert AnomalyType.RESERVED_IP in result.anomalies
    
    def test_private_class_a(self):
        """测试 A 类私网"""
        result = ProxyValidator.validate_ip('10.0.0.1')
        assert not result.is_valid
        assert AnomalyType.PRIVATE_IP in result.anomalies


class TestProxyValidatorPort:
    """测试端口验证"""
    
    def test_valid_port(self):
        """测试有效端口"""
        result = ProxyValidator.validate_port(8080)
        assert result.is_valid
        assert result.confidence == 1.0
    
    def test_port_boundary_min(self):
        """测试最小有效端口"""
        result = ProxyValidator.validate_port(1)
        assert result.is_valid
    
    def test_port_boundary_max(self):
        """测试最大有效端口"""
        result = ProxyValidator.validate_port(65535)
        assert result.is_valid
    
    def test_invalid_port_too_high(self):
        """测试端口过大"""
        result = ProxyValidator.validate_port(99999)
        assert not result.is_valid
        assert AnomalyType.INVALID_PORT in result.anomalies
    
    def test_invalid_port_too_low(self):
        """测试端口过小"""
        result = ProxyValidator.validate_port(0)
        assert not result.is_valid
        assert AnomalyType.INVALID_PORT in result.anomalies
    
    def test_missing_port(self):
        """测试缺少端口"""
        result = ProxyValidator.validate_port(None)
        assert not result.is_valid
        assert AnomalyType.MISSING_PORT in result.anomalies
        assert result.confidence == 0.7  # 可容忍
    
    def test_suspicious_port(self):
        """测试可疑端口"""
        result = ProxyValidator.validate_port(22)  # SSH
        assert result.is_valid  # 仍然有效
        assert len(result.warnings) > 0
        assert result.confidence == 0.85


class TestProxyValidatorProtocol:
    """测试协议验证"""
    
    def test_valid_http_protocol(self):
        """测试有效的 HTTP 协议"""
        result = ProxyValidator.validate_protocol('http')
        assert result.is_valid
        assert result.confidence == 1.0
    
    def test_valid_https_protocol(self):
        """测试有效的 HTTPS 协议"""
        result = ProxyValidator.validate_protocol('https')
        assert result.is_valid
    
    def test_valid_socks5_protocol(self):
        """测试有效的 SOCKS5 协议"""
        result = ProxyValidator.validate_protocol('socks5')
        assert result.is_valid
    
    def test_case_insensitive_protocol(self):
        """测试协议大小写不敏感"""
        result = ProxyValidator.validate_protocol('HTTP')
        assert result.is_valid
    
    def test_invalid_protocol(self):
        """测试无效协议"""
        result = ProxyValidator.validate_protocol('ftp')
        assert not result.is_valid
        assert AnomalyType.UNSUPPORTED_PROTOCOL in result.anomalies
    
    def test_missing_protocol(self):
        """测试缺少协议"""
        result = ProxyValidator.validate_protocol(None)
        assert result.is_valid  # 可选
        assert result.confidence == 0.9


class TestProxyValidatorFull:
    """测试完整代理验证"""
    
    def test_valid_proxy_full(self):
        """测试有效的完整代理"""
        result = ProxyValidator.validate_proxy('1.2.3.4', 8080, 'http')
        assert result.is_valid
        assert result.confidence == 1.0
    
    def test_proxy_with_private_ip(self):
        """测试包含私网 IP 的代理"""
        result = ProxyValidator.validate_proxy('192.168.1.1', 8080, 'http')
        assert not result.is_valid
        assert AnomalyType.PRIVATE_IP in result.anomalies
    
    def test_proxy_with_invalid_port(self):
        """测试包含无效端口的代理"""
        result = ProxyValidator.validate_proxy('1.2.3.4', 99999, 'http')
        assert not result.is_valid
        assert AnomalyType.INVALID_PORT in result.anomalies
    
    def test_proxy_with_unsupported_protocol(self):
        """测试包含不支持协议的代理"""
        result = ProxyValidator.validate_proxy('1.2.3.4', 8080, 'telnet')
        assert not result.is_valid
        assert AnomalyType.UNSUPPORTED_PROTOCOL in result.anomalies
    
    def test_proxy_without_port(self):
        """测试无端口的代理"""
        result = ProxyValidator.validate_proxy('1.2.3.4', None, 'http')
        assert not result.is_valid  # 需要端口
        assert AnomalyType.MISSING_PORT in result.anomalies


class TestProxyValidatorDuplicates:
    """测试重复检测"""
    
    def test_detect_duplicates(self):
        """测试检测重复代理"""
        proxies = [
            ('1.2.3.4', 8080, 'http'),
            ('1.2.3.4', 8080, 'http'),
            ('5.6.7.8', 9090, 'https'),
        ]
        
        duplicates = ProxyValidator.detect_duplicates(proxies)
        
        # 应该找到第一个代理的重复
        assert len(duplicates) == 1
    
    def test_no_duplicates(self):
        """测试无重复代理"""
        proxies = [
            ('1.2.3.4', 8080, 'http'),
            ('5.6.7.8', 9090, 'https'),
        ]
        
        duplicates = ProxyValidator.detect_duplicates(proxies)
        
        assert len(duplicates) == 0


class TestProxyValidatorBatch:
    """测试批量验证"""
    
    def test_batch_validate_mixed(self):
        """测试批量验证混合数据"""
        proxies = [
            {'ip': '1.2.3.4', 'port': 8080, 'protocol': 'http'},
            {'ip': '192.168.1.1', 'port': 8080, 'protocol': 'http'},
            {'ip': '5.6.7.8', 'port': 9090, 'protocol': 'https'},
            {'ip': '10.0.0.1', 'port': 99999, 'protocol': 'http'},
        ]
        
        valid_proxies, stats = ProxyValidator.batch_validate(proxies)
        
        # 应该有 2 个有效代理（第 1 和第 3 个）
        assert stats['total'] == 4
        assert stats['valid'] == 2
        assert stats['invalid'] == 2
        assert len(valid_proxies) == 2
    
    def test_batch_validate_statistics(self):
        """测试批量验证统计"""
        proxies = [
            {'ip': '1.2.3.4', 'port': 8080, 'protocol': 'http'},
            {'ip': '192.168.1.1', 'port': 8080, 'protocol': 'http'},
        ]
        
        _, stats = ProxyValidator.batch_validate(proxies)
        
        # 检查统计
        assert 'anomaly_distribution' in stats
        assert stats['invalid'] == 1
        assert 'private_ip' in stats['anomaly_distribution']


class TestProxyValidatorEdgeCases:
    """边界情况测试"""
    
    def test_broadcast_address(self):
        """测试广播地址"""
        result = ProxyValidator.validate_ip('255.255.255.255')
        assert not result.is_valid
        assert AnomalyType.BROADCAST_IP in result.anomalies
    
    def test_zero_address(self):
        """测试 0 地址"""
        result = ProxyValidator.validate_ip('0.0.0.0')
        assert not result.is_valid
    
    def test_validation_result_dataclass(self):
        """测试 ValidationResult 数据类"""
        result = ValidationResult(
            is_valid=True,
            confidence=0.95,
            anomalies=[],
            warnings=['test warning']
        )
        
        assert result.is_valid
        assert result.confidence == 0.95
        assert len(result.warnings) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
