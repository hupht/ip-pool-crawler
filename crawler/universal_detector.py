"""
通用 IP 检测器模块

自动检测 HTML 中的 IP 地址、端口和相关特征
支持多种格式：IP、IP:PORT、协议等
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from enum import Enum


class MatchType(Enum):
    """匹配类型"""
    IP_ONLY = "ip_only"                      # 仅 IP
    IP_PORT = "ip_port"                      # IP:PORT
    IP_PORT_PROTOCOL = "ip_port_protocol"    # IP:PORT with protocol
    PROTOCOL = "protocol"                    # 仅协议
    PORT = "port"                            # 仅端口


@dataclass
class IPMatch:
    """IP 匹配结果"""
    match_type: MatchType
    ip: Optional[str] = None              # IP 地址
    port: Optional[int] = None            # 端口
    protocol: Optional[str] = None        # 协议 (http/https/socks5 等)
    matched_text: str = ""                # 原始匹配文本
    position: Tuple[int, int] = (0, 0)    # (start, end) 位置
    context: str = ""                     # 周边上下文（前后 30 个字符）
    confidence: float = 0.5               # 置信度 0-1
    
    def __str__(self):
        if self.port:
            return f"{self.ip}:{self.port}"
        return self.ip or ""


class UniversalDetector:
    """通用 IP 检测器"""
    
    # 有效的协议列表
    PROTOCOLS = {
        'http', 'https', 'socks4', 'socks5', 'socks4a',
        'sock4', 'sock5', 'connect', 'proxy'
    }
    
    # 正则表达式模式
    # IP 地址：支持 0-255 的四字节
    IP_PATTERN = r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
    
    # IP:PORT 模式
    IP_PORT_PATTERN = rf'({IP_PATTERN}):(\d{{1,5}})'
    
    # 协议模式（前面可能有空格、=、:）
    PROTOCOL_PATTERN = r'(?:[\s=:]\s*(?P<protocol>http|https|socks4|socks5|socks4a|sock4|sock5|connect|proxy))\s+'
    
    # 端口单独模式（从"port"、"port:"等上下文提取）
    PORT_PATTERN = r'(?:port|:port|端口)[\s:=]*(\d{1,5})'
    
    @staticmethod
    def _get_context(html: str, start: int, end: int, window: int = 50) -> str:
        """获取匹配位置的前后上下文"""
        ctx_start = max(0, start - window)
        ctx_end = min(len(html), end + window)
        return html[ctx_start:ctx_end].strip()
    
    @staticmethod
    def _validate_ip(ip: str) -> bool:
        """验证 IP 地址的有效性"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except:
            return False
    
    @staticmethod
    def _validate_port(port: int) -> bool:
        """验证端口的有效性"""
        return 1 <= port <= 65535
    
    @classmethod
    def detect_ip_port_pairs(cls, html: str) -> List[IPMatch]:
        """
        检测 HTML 中的 IP:PORT 对
        
        Args:
            html: HTML 内容
            
        Returns:
            IPMatch 列表
        """
        matches = []
        
        for match in re.finditer(cls.IP_PORT_PATTERN, html):
            ip = match.group(1)
            port_str = match.group(2)
            
            # 验证 IP
            if not cls._validate_ip(ip):
                continue
            
            try:
                port = int(port_str)
                # 验证端口
                if not cls._validate_port(port):
                    continue
            except ValueError:
                continue
            
            # 提取上下文  
            context = cls._get_context(html, match.start(), match.end())
            
            # 尝试从上下文识别协议
            protocol = cls._extract_protocol_from_context(context)
            
            matches.append(IPMatch(
                match_type=MatchType.IP_PORT,
                ip=ip,
                port=port,
                protocol=protocol,
                matched_text=match.group(0),
                position=(match.start(), match.end()),
                context=context,
                confidence=0.95,  # IP:PORT 对的置信度最高
            ))
        
        return matches
    
    @classmethod
    def detect_ips(cls, html: str) -> List[IPMatch]:
        """
        检测 HTML 中的独立 IP 地址
        
        Args:
            html: HTML 内容
            
        Returns:
            IPMatch 列表
        """
        matches = []
        seen = set()
        
        for match in re.finditer(cls.IP_PATTERN, html):
            ip = match.group(0)
            
            # 验证 IP
            if not cls._validate_ip(ip):
                continue
            
            # 避免重复检测
            if (ip, match.start()) in seen:
                continue
            seen.add((ip, match.start()))
            
            # 提取上下文
            context = cls._get_context(html, match.start(), match.end())
            
            # 尝试从上下文找端口和协议
            port = cls._extract_port_from_context(context)
            protocol = cls._extract_protocol_from_context(context)
            
            # 计算置信度
            if port:
                confidence = 0.85  # 找到端口增加置信度
            else:
                confidence = 0.6   # 仅 IP 的置信度
            
            match_type = MatchType.IP_PORT if port else MatchType.IP_ONLY
            
            matches.append(IPMatch(
                match_type=match_type,
                ip=ip,
                port=port,
                protocol=protocol,
                matched_text=match.group(0),
                position=(match.start(), match.end()),
                context=context,
                confidence=confidence,
            ))
        
        return matches
    
    @classmethod
    def detect_ports(cls, html: str) -> List[int]:
        """
        检测 HTML 中的端口列表

        Args:
            html: HTML 内容

        Returns:
            端口列表（去重，保持出现顺序）
        """
        ports: List[int] = []
        seen = set()

        for match in re.finditer(cls.IP_PORT_PATTERN, html):
            try:
                port = int(match.group(2))
            except ValueError:
                continue
            if cls._validate_port(port) and port not in seen:
                seen.add(port)
                ports.append(port)

        for match in re.finditer(cls.PORT_PATTERN, html, re.IGNORECASE):
            try:
                port = int(match.group(1))
            except ValueError:
                continue
            if cls._validate_port(port) and port not in seen:
                seen.add(port)
                ports.append(port)

        return ports

    @classmethod
    def detect_protocols(cls, html: str) -> List[str]:
        """
        检测 HTML 中的协议字段
        
        Args:
            html: HTML 内容
            
        Returns:
            协议名称列表（去重，保持出现顺序）
        """
        protocols: List[str] = []
        seen = set()
        
        # 简单的协议检测：在 HTML 中查找常见的协议字段
        pattern = r'(?:protocol|协议)[\s:=\"]*([\'"]?)(' + '|'.join(cls.PROTOCOLS) + r')\1'
        
        for match in re.finditer(pattern, html, re.IGNORECASE):
            protocol = match.group(2).lower()
            if protocol not in seen:
                seen.add(protocol)
                protocols.append(protocol)
        
        return protocols
    
    @staticmethod
    def _extract_port_from_context(context: str) -> Optional[int]:
        """从上下文提取端口"""
        # 查找 :port 模式
        match = re.search(r':(\d{1,5})', context)
        if match:
            try:
                port = int(match.group(1))
                if UniversalDetector._validate_port(port):
                    return port
            except ValueError:
                pass
        
        # 查找 port=XXX 或 port: XXX 模式
        match = re.search(r'port[=: ]+(\d{1,5})', context, re.IGNORECASE)
        if match:
            try:
                port = int(match.group(1))
                if UniversalDetector._validate_port(port):
                    return port
            except ValueError:
                pass
        
        return None
    
    @staticmethod
    def _extract_protocol_from_context(context: str) -> Optional[str]:
        """从上下文提取协议"""
        protocols = ['https', 'socks5', 'socks4a', 'socks4', 'http', 'connect', 'proxy']
        context_lower = context.lower()

        # 查找协议模式（按长度优先，避免 https 被 http 提前命中）
        for protocol in protocols:
            if re.search(rf'\b{re.escape(protocol)}\b', context_lower):
                return protocol
        
        return None
    
    @classmethod
    def detect_all(cls, html: str) -> Dict[str, List]:
        """
        检测 HTML 中的所有 IP 相关特征
        
        Args:
            html: HTML 内容
            
        Returns:
            {
                'ip_port_pairs': [...],
                'ips': [...],
                'protocols': [...]
            }
        """
        return {
            'ip_port_pairs': cls.detect_ip_port_pairs(html),
            'ips': cls.detect_ips(html),
            'protocols': cls.detect_protocols(html),
        }


if __name__ == "__main__":
    # 快速测试
    test_html = """
    <tr>
        <td>1.2.3.4</td>
        <td>8080</td>
        <td>http</td>
    </tr>
    <p>Proxy: 5.6.7.8:9090 (https)</p>
    <div>IP Address: 10.11.12.13</div>
    """
    
    detector = UniversalDetector()
    results = detector.detect_all(test_html)
    
    print("IP:PORT 对:")
    for match in results['ip_port_pairs']:
        print(f"  {match}")
    
    print("\nIP 地址:")
    for match in results['ips']:
        print(f"  {match}")
    
    print("\n协议:")
    for proto in results['protocols']:
        print(f"  {proto}")
