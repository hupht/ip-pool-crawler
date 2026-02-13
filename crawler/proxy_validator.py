"""
代理验证器和异常检测模块

验证代理数据的有效性，检测异常模式
"""

import re
import socket
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Set, Tuple
from ipaddress import IPv4Address, IPv4Network, ip_address


class AnomalyType(Enum):
    """异常类型"""
    PRIVATE_IP = "private_ip"              # 私有 IP
    RESERVED_IP = "reserved_ip"            # 保留 IP
    BROADCAST_IP = "broadcast_ip"          # 广播地址
    INVALID_IP = "invalid_ip"              # 无效 IP
    INVALID_PORT = "invalid_port"          # 无效端口
    MISSING_PORT = "missing_port"          # 缺少端口
    UNSUPPORTED_PROTOCOL = "unsupported_protocol"  # 不支持的协议
    DUPLICATE_PROXY = "duplicate_proxy"    # 重复代理
    SUSPICIOUS_PATTERN = "suspicious_pattern"  # 可疑模式


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool                         # 是否有效
    confidence: float = 1.0                # 置信度
    anomalies: List[AnomalyType] = field(default_factory=list)  # 异常类型
    anomaly_details: Dict[str, Any] = field(default_factory=dict)  # 异常详情
    warnings: List[str] = field(default_factory=list)  # 警告信息


class ProxyValidator:
    """代理验证器和异常检测器"""
    
    # 常见的 SOCKS 代理服务的已知 IP 范围
    SUSPICIOUS_CIDR_PATTERNS = [
        # 某些已知的恶意 IP 范围（演示用，实际应连接真实列表）
        # "192.168.0.0/16",  # 私网
        # "10.0.0.0/8",      # 私网
    ]
    
    # 支持的协议列表
    SUPPORTED_PROTOCOLS = {'http', 'https', 'socks4', 'socks5', 'socks4a'}
    
    # 常见但可疑的端口
    SUSPICIOUS_PORTS = {
        22, 23, 25, 53, 135, 139, 445,  # SSH, Telnet, SMTP, DNS, SMB 等
        3389,  # RDP
        5900,  # VNC
    }
    
    @staticmethod
    def validate_ip(ip: str) -> ValidationResult:
        """
        验证 IP 地址
        
        Args:
            ip: IP 地址
            
        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True, confidence=1.0)
        
        if not ip:
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                anomalies=[AnomalyType.INVALID_IP],
                anomaly_details={"error": "Empty IP"}
            )
        
        try:
            ip_obj = IPv4Address(ip)
        except ValueError:
            # 不是有效的 IPv4 地址
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                anomalies=[AnomalyType.INVALID_IP],
                anomaly_details={"error": f"Invalid IPv4 format: {ip}"}
            )
        
        # 检查私有 IP
        if ip_obj.is_private:
            result.anomalies.append(AnomalyType.PRIVATE_IP)
            result.anomaly_details['private_ip'] = True
            result.is_valid = False
            result.confidence = 0.2  # 严重问题
        
        # 检查保留地址
        if ip_obj.is_reserved:
            result.anomalies.append(AnomalyType.RESERVED_IP)
            result.anomaly_details['reserved'] = True
            if not result.anomalies:  # 仅当没有更严重的问题时
                result.is_valid = False
                result.confidence = 0.3
        
        # 检查广播地址
        if ip_obj.is_multicast or str(ip_obj) == '255.255.255.255':
            result.anomalies.append(AnomalyType.BROADCAST_IP)
            result.anomaly_details['broadcast'] = True
            result.is_valid = False
            result.confidence = 0.1
        
        # 检查回环地址（localhost）
        if ip_obj.is_loopback:
            result.anomalies.append(AnomalyType.RESERVED_IP)
            result.anomaly_details['loopback'] = True
            result.is_valid = False
            result.confidence = 0.1
        
        return result
    
    @staticmethod
    def validate_port(port: Optional[int]) -> ValidationResult:
        """
        验证端口号
        
        Args:
            port: 端口号
            
        Returns:
            验证结果
        """
        if port is None:
            return ValidationResult(
                is_valid=False,
                confidence=0.7,
                anomalies=[AnomalyType.MISSING_PORT],
                warnings=["Port is missing, using default port"]
            )
        
        if not isinstance(port, int):
            try:
                port = int(port)
            except (ValueError, TypeError):
                return ValidationResult(
                    is_valid=False,
                    confidence=0.0,
                    anomalies=[AnomalyType.INVALID_PORT],
                    anomaly_details={"error": f"Invalid port format: {port}"}
                )
        
        if not (1 <= port <= 65535):
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                anomalies=[AnomalyType.INVALID_PORT],
                anomaly_details={"error": f"Port out of range: {port}"}
            )
        
        result = ValidationResult(is_valid=True, confidence=1.0)
        
        # 检查可疑端口
        if port in ProxyValidator.SUSPICIOUS_PORTS:
            result.warnings.append(f"Suspicious port: {port}")
            result.confidence = 0.85
        
        return result
    
    @staticmethod
    def validate_protocol(protocol: Optional[str]) -> ValidationResult:
        """
        验证协议
        
        Args:
            protocol: 协议字符串
            
        Returns:
            验证结果
        """
        if not protocol:
            return ValidationResult(
                is_valid=True,
                confidence=0.9,
                warnings=["Protocol not specified"]
            )
        
        protocol_lower = protocol.lower().strip()
        
        if protocol_lower not in ProxyValidator.SUPPORTED_PROTOCOLS:
            return ValidationResult(
                is_valid=False,
                confidence=0.3,
                anomalies=[AnomalyType.UNSUPPORTED_PROTOCOL],
                anomaly_details={"unsupported": protocol_lower},
                warnings=[f"Unsupported protocol: {protocol}"]
            )
        
        return ValidationResult(is_valid=True, confidence=1.0)
    
    @staticmethod
    def validate_proxy(ip: str, port: Optional[int] = None, 
                      protocol: Optional[str] = None) -> ValidationResult:
        """
        验证完整的代理（IP:Port:Protocol）
        
        Args:
            ip: IP 地址
            port: 端口号
            protocol: 协议
            
        Returns:
            综合验证结果
        """
        # 验证各组件
        ip_result = ProxyValidator.validate_ip(ip)
        port_result = ProxyValidator.validate_port(port)
        protocol_result = ProxyValidator.validate_protocol(protocol)
        
        # 合并结果
        combined = ValidationResult(is_valid=True, confidence=1.0)
        
        # 合并异常和警告
        combined.anomalies.extend(ip_result.anomalies)
        combined.anomalies.extend(port_result.anomalies)
        combined.anomalies.extend(protocol_result.anomalies)
        
        combined.warnings.extend(ip_result.warnings)
        combined.warnings.extend(port_result.warnings)
        combined.warnings.extend(protocol_result.warnings)
        
        # 合并详情
        combined.anomaly_details.update(ip_result.anomaly_details)
        combined.anomaly_details.update(port_result.anomaly_details)
        combined.anomaly_details.update(protocol_result.anomaly_details)
        
        # 重新计算有效性
        combined.is_valid = ip_result.is_valid and port_result.is_valid and protocol_result.is_valid
        
        # 重新计算置信度（取最小值）
        combined.confidence = min(ip_result.confidence, port_result.confidence, protocol_result.confidence)
        
        return combined
    
    @staticmethod
    def detect_duplicates(proxies: List[Tuple[str, Optional[int], Optional[str]]]) -> Dict[str, List[int]]:
        """
        检测重复的代理
        
        Args:
            proxies: (IP, Port, Protocol) 元组列表
            
        Returns:
            重复代理的映射 {uniqueKey: [index1, index2, ...]}
        """
        seen = {}
        duplicates = {}
        
        for idx, (ip, port, protocol) in enumerate(proxies):
            # 创建唯一键
            key = (ip, port, protocol or 'unknown')
            
            if key in seen:
                if key not in duplicates:
                    duplicates[str(key)] = [seen[key]]
                duplicates[str(key)].append(idx)
            else:
                seen[key] = idx
        
        return duplicates
    
    @staticmethod
    def detect_anomaly_pattern(ip: str, port: Optional[int] = None) -> Optional[AnomalyType]:
        """
        检测可疑的代理模式
        
        Args:
            ip: IP 地址
            port: 端口号
            
        Returns:
            异常类型或 None
        """
        # 模式 1: 相同 IP 不同端口太多
        # 模式 2: 连续 IP （可能是蜜罐）
        # 模式 3: 已知的恶意 IP 范围
        
        try:
            ip_obj = ip_address(ip)
            
            # 检查已知的恶意 CIDR
            for cidr_str in ProxyValidator.SUSPICIOUS_CIDR_PATTERNS:
                cidr = IPv4Network(cidr_str)
                if ip_obj in cidr:
                    return AnomalyType.SUSPICIOUS_PATTERN
        except ValueError:
            pass
        
        return None
    
    @staticmethod
    def batch_validate(proxies: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        批量验证代理列表
        
        Args:
            proxies: 代理字典列表 [{'ip': '...', 'port': ..., 'protocol': '...'}]
            
        Returns:
            (验证通过的代理, 验证统计信息)
        """
        valid_proxies = []
        statistics = {
            'total': len(proxies),
            'valid': 0,
            'invalid': 0,
            'warnings': 0,
            'anomaly_distribution': {},
            'invalid_reasons': []
        }
        
        for proxy in proxies:
            ip = proxy.get('ip')
            port = proxy.get('port')
            protocol = proxy.get('protocol')
            
            result = ProxyValidator.validate_proxy(ip, port, protocol)
            
            if result.is_valid:
                statistics['valid'] += 1
                valid_proxies.append(proxy)
            else:
                statistics['invalid'] += 1
            
            if result.warnings:
                statistics['warnings'] += len(result.warnings)
            
            # 统计异常类型
            for anomaly in result.anomalies:
                anomaly_name = anomaly.value
                if anomaly_name not in statistics['anomaly_distribution']:
                    statistics['anomaly_distribution'][anomaly_name] = 0
                statistics['anomaly_distribution'][anomaly_name] += 1
                
                if not result.is_valid:
                    statistics['invalid_reasons'].append({
                        'ip': ip,
                        'anomaly': anomaly_name,
                        'confidence': result.confidence
                    })
        
        return valid_proxies, statistics


if __name__ == "__main__":
    # 快速测试
    validator = ProxyValidator()
    
    # 测试 IP 验证
    print("IP 验证:")
    print(f"  1.2.3.4: {validator.validate_ip('1.2.3.4').is_valid}")
    print(f"  192.168.1.1: {validator.validate_ip('192.168.1.1').is_valid}")
    print(f"  127.0.0.1: {validator.validate_ip('127.0.0.1').is_valid}")
    
    # 测试端口验证
    print("\n端口验证:")
    print(f"  8080: {validator.validate_port(8080).is_valid}")
    print(f"  99999: {validator.validate_port(99999).is_valid}")
    
    # 测试协议验证
    print("\n协议验证:")
    print(f"  http: {validator.validate_protocol('http').is_valid}")
    print(f"  ftp: {validator.validate_protocol('ftp').is_valid}")
