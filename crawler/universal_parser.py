"""
通用数据解析器模块

从各种 HTML 结构中提取代理数据（IP、Port、Protocol）
支持表格、列表、JSON 等多种格式
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Union
from crawler.structure_analyzer import StructureAnalyzer, Table, HTMLList, JSONBlock
from crawler.universal_detector import UniversalDetector


@dataclass
class ProxyExtraction:
    """代理提取结果"""
    ip: str                          # IP 地址
    port: Optional[int] = None       # 端口
    protocol: Optional[str] = None   # 协议
    source_type: str = "unknown"     # 数据源类型 (table/list/json/text)
    confidence: float = 0.0          # 置信度 (0.0-1.0)
    raw_data: Optional[str] = None   # 原始数据
    additional_info: Dict[str, Any] = field(default_factory=dict)  # 额外信息


class UniversalParser:
    """通用数据解析器"""

    @staticmethod
    def _decode_html(html: Union[str, bytes]) -> str:
        if isinstance(html, str):
            return html

        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                return html.decode(encoding)
            except UnicodeDecodeError:
                continue

        return html.decode("utf-8", errors="ignore")

    @staticmethod
    def parse(
        html: Union[str, bytes],
        structure: Optional[Dict[str, Any]] = None,
        user_prompt: Optional[str] = None,
    ) -> List[ProxyExtraction]:
        del user_prompt

        html_text = UniversalParser._decode_html(html)

        if structure is None:
            structure = StructureAnalyzer.analyze_all(html_text)

        table_proxies = UniversalParser.extract_from_tables(structure.get('tables', []))
        json_proxies = UniversalParser.extract_from_json(structure.get('json_blocks', []))
        text_proxies = UniversalParser.extract_from_text(structure.get('text_blocks', []))
        list_proxies = UniversalParser.extract_from_lists(structure.get('lists', []))

        merged = table_proxies + json_proxies + text_proxies + list_proxies
        return UniversalParser.deduplicate_proxies(merged)
    
    @staticmethod
    def extract_from_tables(tables: List[Table]) -> List[ProxyExtraction]:
        """
        从表格中提取代理数据
        
        Args:
            tables: 表格数据列表
            
        Returns:
            代理提取结果列表
        """
        extractions = []
        
        for table in tables:
            # 猜测列索引
            ip_col = StructureAnalyzer.guess_column_index(table.headers, 'ip')
            port_col = StructureAnalyzer.guess_column_index(table.headers, 'port')
            protocol_col = StructureAnalyzer.guess_column_index(table.headers, 'protocol')
            
            # 如果没找到 IP 列，跳过
            if ip_col is None:
                continue
            
            # 遍历表格行
            for row_idx, row in enumerate(table.rows):
                ip_cell = row[ip_col] if ip_col < len(row) else None
                port_cell = row[port_col] if port_col is not None and port_col < len(row) else None
                protocol_cell = row[protocol_col] if protocol_col is not None and protocol_col < len(row) else None
                
                # 检测 IP 地址
                ip_matches = UniversalDetector.detect_ips(ip_cell or "")
                
                for ip_match in ip_matches:
                    # 提取 Port
                    port = None
                    if port_cell:
                        # 先尝试转换为整数
                        try:
                            port_int = int(port_cell.strip())
                            if 1 <= port_int <= 65535:
                                port = port_int
                        except ValueError:
                            # 尝试从单元格中提取数字
                            numbers = re.findall(r'\d+', port_cell)
                            if numbers:
                                try:
                                    port = int(numbers[0])
                                    if not (1 <= port <= 65535):
                                        port = None
                                except ValueError:
                                    pass
                    
                    # 提取协议
                    protocol = None
                    if protocol_cell:
                        protocol_matches = UniversalDetector.detect_protocols(protocol_cell)
                        if protocol_matches:
                            protocol = protocol_matches[0]
                        else:
                            # 如果 detect_protocols 没找到，尝试直接识别常见协议
                            # 从最长的协议开始（确保 https 在 http 之前）
                            protocol_cell_lower = protocol_cell.lower().strip()
                            for prot in ['https', 'socks5', 'socks4', 'http', 'socks']:
                                if prot in protocol_cell_lower:
                                    protocol = prot
                                    break
                    
                    extraction = ProxyExtraction(
                        ip=ip_match.ip,
                        port=port,
                        protocol=protocol,
                        source_type="table",
                        confidence=0.95,  # 表格提取高置信度
                        raw_data="|".join(row),
                        additional_info={
                            "row_index": row_idx,
                            "table_headers": table.headers
                        }
                    )
                    extractions.append(extraction)
        
        return extractions
    
    @staticmethod
    def extract_from_lists(lists: List[HTMLList]) -> List[ProxyExtraction]:
        """
        从列表中提取代理数据
        
        Args:
            lists: 列表数据列表
            
        Returns:
            代理提取结果列表
        """
        extractions = []
        
        for list_obj in lists:
            for item_idx, item in enumerate(list_obj.items):
                # 检测 IP:PORT 对
                ip_port_matches = UniversalDetector.detect_ip_port_pairs(item)
                
                for match in ip_port_matches:
                    extraction = ProxyExtraction(
                        ip=match.ip,
                        port=match.port,
                        protocol=match.protocol,
                        source_type="list",
                        confidence=match.confidence,
                        raw_data=item,
                        additional_info={
                            "item_index": item_idx,
                            "list_type": list_obj.list_type
                        }
                    )
                    extractions.append(extraction)
                
                # 如果列表项包含 IP 但没有 PORT，也提取
                if not ip_port_matches:
                    ip_only_matches = UniversalDetector.detect_ips(item)
                    for match in ip_only_matches:
                        extraction = ProxyExtraction(
                            ip=match.ip,
                            port=match.port,
                            protocol=match.protocol,
                            source_type="list",
                            confidence=min(match.confidence, 0.85),
                            raw_data=item,
                            additional_info={
                                "item_index": item_idx,
                                "list_type": list_obj.list_type
                            }
                        )
                        extractions.append(extraction)
        
        return extractions
    
    @staticmethod
    def extract_from_json(json_blocks: List[JSONBlock]) -> List[ProxyExtraction]:
        """
        从 JSON 块中提取代理数据
        
        Args:
            json_blocks: JSON 块列表
            
        Returns:
            代理提取结果列表
        """
        extractions = []
        
        for block in json_blocks:
            try:
                data = block.data
                
                # 容错：如果是字符串，尝试再次解析
                if isinstance(data, str):
                    data = json.loads(data)
                
                # 处理不同的 JSON 结构
                extracted = UniversalParser._extract_from_json_data(data)
                
                for proxy_data in extracted:
                    extraction = ProxyExtraction(
                        ip=proxy_data.get('ip'),
                        port=proxy_data.get('port'),
                        protocol=proxy_data.get('protocol'),
                        source_type="json",
                        confidence=0.95,
                        raw_data=json.dumps(proxy_data)[:100],
                        additional_info=proxy_data
                    )
                    
                    # 只添加有效的 IP 地址
                    if extraction.ip:
                        extractions.append(extraction)
                        
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        
        return extractions
    
    @staticmethod
    def _extract_from_json_data(data: Any) -> List[Dict[str, Any]]:
        """
        递归提取 JSON 中的代理数据
        
        Args:
            data: JSON 数据
            
        Returns:
            代理数据字典列表
        """
        proxies = []
        
        if isinstance(data, list):
            # 列表：遍历每个元素
            for item in data:
                proxies.extend(UniversalParser._extract_from_json_data(item))
        
        elif isinstance(data, dict):
            # 字典：检查是否是代理对象或包含代理列表
            
            # 模式 1: 直接是代理对象 {"ip": "...", "port": ...}
            if 'ip' in data or 'address' in data or 'host' in data:
                ip_val = data.get('ip') or data.get('address') or data.get('host')
                port_val = data.get('port')
                protocol_val = data.get('protocol') or data.get('type')
                
                if ip_val:
                    proxies.append({
                        'ip': str(ip_val),
                        'port': int(port_val) if port_val else None,
                        'protocol': str(protocol_val) if protocol_val else None
                    })
                return proxies
            
            # 模式 2: 值是列表 {"proxies": [...]}
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    proxies.extend(UniversalParser._extract_from_json_data(value))
        
        return proxies
    
    @staticmethod
    def extract_from_text(text_blocks: List[str]) -> List[ProxyExtraction]:
        """
        从纯文本块中提取代理数据
        
        Args:
            text_blocks: 文本块列表
            
        Returns:
            代理提取结果列表
        """
        extractions = []
        
        for block_idx, block in enumerate(text_blocks):
            # 检测 IP:PORT 对
            ip_port_matches = UniversalDetector.detect_ip_port_pairs(block)
            
            for match in ip_port_matches:
                extraction = ProxyExtraction(
                    ip=match.ip,
                    port=match.port,
                    protocol=match.protocol,
                    source_type="text",
                    confidence=match.confidence,
                    raw_data=block[:100],
                    additional_info={
                        "block_index": block_idx
                    }
                )
                extractions.append(extraction)
        
        return extractions
    
    @staticmethod
    def extract_all(html: str) -> Tuple[List[ProxyExtraction], Dict[str, Any]]:
        """
        从 HTML 中提取所有代理数据
        
        Args:
            html: HTML 内容
            
        Returns:
            (代理列表, 统计信息)
        """
        html_text = UniversalParser._decode_html(html)

        # 分析 HTML 结构
        analysis = StructureAnalyzer.analyze_all(html_text)

        # 从各种来源提取代理
        table_proxies = UniversalParser.extract_from_tables(analysis['tables'])
        list_proxies = UniversalParser.extract_from_lists(analysis['lists'])
        json_proxies = UniversalParser.extract_from_json(analysis['json_blocks'])
        text_proxies = UniversalParser.extract_from_text(analysis['text_blocks'])
        
        # 合并结果
        all_proxies = table_proxies + list_proxies + json_proxies + text_proxies
        
        # 生成统计信息
        stats = {
            'total_extracted': len(all_proxies),
            'from_tables': len(table_proxies),
            'from_lists': len(list_proxies),
            'from_json': len(json_proxies),
            'from_text': len(text_proxies),
            'by_confidence': {
                'high': len([p for p in all_proxies if p.confidence >= 0.9]),
                'medium': len([p for p in all_proxies if 0.7 <= p.confidence < 0.9]),
                'low': len([p for p in all_proxies if p.confidence < 0.7]),
            }
        }
        
        return all_proxies, stats
    
    @staticmethod
    def deduplicate_proxies(proxies: List[ProxyExtraction]) -> List[ProxyExtraction]:
        """
        去重代理数据（基于 IP:PORT:Protocol）
        
        Args:
            proxies: 代理列表
            
        Returns:
            去重后的代理列表（保留置信度最高的）
        """
        seen = {}
        
        for proxy in proxies:
            # 创建唯一键：IP:PORT:Protocol
            key = (proxy.ip, proxy.port, proxy.protocol)
            
            # 保留置信度最高的
            if key not in seen or proxy.confidence > seen[key].confidence:
                seen[key] = proxy
        
        return list(seen.values())


if __name__ == "__main__":
    # 快速测试
    test_html = """
    <html>
    <body>
        <table>
            <tr><th>IP</th><th>Port</th><th>Protocol</th></tr>
            <tr><td>1.2.3.4</td><td>8080</td><td>http</td></tr>
            <tr><td>5.6.7.8</td><td>9090</td><td>https</td></tr>
        </table>
        
        <ul>
            <li>10.11.12.13:3128</li>
            <li>100.101.102.103:8888</li>
        </ul>
        
        <pre>{"proxies": [{"ip": "200.201.202.203", "port": 80}]}</pre>
    </body>
    </html>
    """
    
    proxies, stats = UniversalParser.extract_all(test_html)
    
    print("提取的代理:")
    for proxy in proxies:
        print(f"  {proxy.ip}:{proxy.port or 'N/A'} ({proxy.protocol or 'N/A'}) - {proxy.source_type} - {proxy.confidence:.2f}")
    
    print(f"\n统计: {stats}")
