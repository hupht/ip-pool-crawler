"""
HTML 结构分析器模块

识别页面中的表格、列表、JSON 数据块等结构
用于帮助通用解析器提取数据
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup


@dataclass
class Table:
    """HTML 表格结构"""
    headers: List[str]                   # 列标题
    rows: List[List[str]]                # 行数据
    footers: List[str] = field(default_factory=list)  # 页脚信息
    html_element: Optional[str] = None   # 原始 HTML
    position: tuple = (0, 0)             # (start, end)
    confidence: float = 0.9              # 置信度


@dataclass
class HTMLList:
    """HTML 列表结构"""
    items: List[str]                     # 列表项
    list_type: str = "ul"                # ul, ol, div 等
    html_element: Optional[str] = None
    position: tuple = (0, 0)
    confidence: float = 0.8


@dataclass
class JSONBlock:
    """JSON 数据块"""
    data: Dict[str, Any]                 # 解析后的 JSON 数据
    raw_text: str = ""                   # 原始文本
    position: tuple = (0, 0)
    confidence: float = 0.95


class StructureAnalyzer:
    """HTML 结构分析器"""
    
    # 常见的表格列名（中英文、模糊）
    COLUMN_ALIASES = {
        'ip': ['ip', 'ip地址', 'ip address', 'host', '主机', '地址', 'address'],
        'port': ['port',  '端口', '端口号', 'port号'],
        'protocol': ['protocol', '协议', 'type', '类型', 'proto'],
        'anonymity': ['anonymity', '匿名', '匿名度', 'level', '等级'],
        'country': ['country', '国家', '地区', 'location', '位置'],
        'status': ['status', '状态', 'available', '可用性'],
        'speed': ['speed', '速度', '响应时间', 'response time'],
    }
    
    @classmethod
    def find_tables(cls, html: str) -> List[Table]:
        """
        查找 HTML 中的所有表格
        
        Args:
            html: HTML 内容
            
        Returns:
            表格列表
        """
        tables = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception:
            # 如果解析失败，返回空
            return tables
        
        for table_element in soup.find_all('table'):
            try:
                # 提取表头
                headers = []
                header_row = table_element.find('tr')
                if header_row:
                    for th in header_row.find_all(['th', 'td']):
                        headers.append(th.get_text(strip=True))
                
                # 提取数据行
                rows = []
                for tr in table_element.find_all('tr')[1:]:  # 跳过表头行
                    row = []
                    for td in tr.find_all('td'):
                        row.append(td.get_text(strip=True))
                    if row:
                        rows.append(row)

                # 提取页脚
                footers: List[str] = []
                tfoot = table_element.find('tfoot')
                if tfoot:
                    for tr in tfoot.find_all('tr'):
                        cells = [cell.get_text(strip=True) for cell in tr.find_all(['th', 'td'])]
                        line = " | ".join([cell for cell in cells if cell])
                        if line:
                            footers.append(line)
                
                # 只有有数据的表格才添加
                if headers or rows:
                    table = Table(
                        headers=headers if headers else [],
                        rows=rows,
                        footers=footers,
                        html_element=str(table_element)[:200],  # 只保存前 200 字符
                        confidence=0.95 if headers else 0.8
                    )
                    tables.append(table)
            except Exception:
                continue
        
        return tables
    
    @classmethod
    def find_lists(cls, html: str) -> List[HTMLList]:
        """
        查找 HTML 中的所有列表结构
        
        Args:
            html: HTML 内容
            
        Returns:
            列表结构列表
        """
        lists = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception:
            return lists
        
        # 查找 <ul> 和 <ol>
        for list_elem in soup.find_all(['ul', 'ol']):
            try:
                items = []
                for li in list_elem.find_all('li', recursive=False):
                    text = li.get_text(strip=True)
                    if text:
                        items.append(text)
                
                if items:
                    html_list = HTMLList(
                        items=items,
                        list_type=list_elem.name,
                        confidence=0.9
                    )
                    lists.append(html_list)
            except Exception:
                continue
        
        # 查找常见的 div 列表模式
        for div in soup.find_all('div', class_=re.compile(r'list|item|row', re.I)):
            try:
                items = []
                
                # 查找子元素
                for child in div.find_all(['div', 'p', 'span'], recursive=False):
                    text = child.get_text(strip=True)
                    if text and len(text) > 5:  # 过滤过短的文本
                        items.append(text)
                
                if len(items) >= 3:  # 至少 3 项才认为是列表
                    html_list = HTMLList(
                        items=items,
                        list_type="div",
                        confidence=0.7
                    )
                    lists.append(html_list)
            except Exception:
                continue
        
        return lists
    
    @classmethod
    def find_json_blocks(cls, html: str) -> List[JSONBlock]:
        """
        查找 HTML 中的 JSON 数据块
        
        Args:
            html: HTML 内容
            
        Returns:
            JSON 块列表
        """
        blocks = []
        
        # 查找 <pre> 或 <code> 标签中的 JSON
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            for elem in soup.find_all(['pre', 'code', 'script']):
                text = elem.get_text(strip=True)
                
                # 尝试解析 JSON
                if cls._try_parse_json(text):
                    try:
                        data = json.loads(text)
                        block = JSONBlock(
                            data=data,
                            raw_text=text[:500],
                            confidence=0.95
                        )
                        blocks.append(block)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
        
        # 查找 HTML 中的 JSON 文本
        json_pattern = r'\{[\s\S]*?\}'
        for match in re.finditer(json_pattern, html):
            text = match.group(0)
            
            # 简单的过滤：太短的不处理
            if len(text) < 20:
                continue
            
            try:
                data = json.loads(text)
                
                # 检查是否包含数组数据
                if isinstance(data, dict) and any(
                    isinstance(v, list) for v in data.values()
                ):
                    block = JSONBlock(
                        data=data,
                        raw_text=text[:500],
                        position=(match.start(), match.end()),
                        confidence=0.85
                    )
                    blocks.append(block)
            except json.JSONDecodeError:
                pass
        
        return blocks
    
    @classmethod
    def find_text_blocks(cls, html: str) -> List[str]:
        """
        查找纯文本数据块（如逗号分隔的 IP 列表）
        
        Args:
            html: HTML 内容
            
        Returns:
            文本块列表
        """
        blocks = []
        
        # 移除标签，保留文本
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # 移除脚本和样式
            for elem in soup(['script', 'style']):
                elem.decompose()
            
            text = soup.get_text('\n')
        except Exception:
            text = html
        
        # 查找看起来像数据的行（包含冒号或逗号）
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            # 过滤
            if not line or len(line) < 5:
                continue
            
            # 如果行包含多个 IP 地址，视为数据块
            ip_count = len(re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', line))
            if ip_count >= 1:
                blocks.append(line)
        
        return blocks
    
    @classmethod
    def guess_column_index(cls, headers: List[str], target: str) -> Optional[int]:
        """
        根据列标题猜测列索引
        
        Args:
            headers: 列标题列表
            target: 目标字段（'ip', 'port' 等）
            
        Returns:
            列索引，如果未找到返回 None
        """
        target_lower = target.lower()
        aliases = cls.COLUMN_ALIASES.get(target_lower, [])
        
        for i, header in enumerate(headers):
            header_lower = header.lower()
            
            # 精确匹配
            if header_lower == target_lower:
                return i
            
            # 别名匹配
            for alias in aliases:
                if alias in header_lower or header_lower in alias:
                    return i
        
        return None
    
    @classmethod
    def analyze_all(cls, html: str) -> Dict[str, Any]:
        """
        分析 HTML 中的所有结构
        
        Args:
            html: HTML 内容
            
        Returns:
            分析结果字典
        """
        return {
            'tables': cls.find_tables(html),
            'lists': cls.find_lists(html),
            'json_blocks': cls.find_json_blocks(html),
            'text_blocks': cls.find_text_blocks(html),
        }
    
    @staticmethod
    def _try_parse_json(text: str) -> bool:
        """尝试解析 JSON，返回是否成功"""
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, ValueError):
            return False


if __name__ == "__main__":
    # 快速测试
    test_html = """
    <table>
        <tr><th>IP</th><th>Port</th><th>Protocol</th></tr>
        <tr><td>1.2.3.4</td><td>8080</td><td>http</td></tr>
        <tr><td>5.6.7.8</td><td>9090</td><td>https</td></tr>
    </table>
    
    <ul>
        <li>1.2.3.4:8080</li>
        <li>5.6.7.8:9090</li>
    </ul>
    
    <pre>
    {"proxies": [
        {"ip": "10.11.12.13", "port": 3128}
    ]}
    </pre>
    """
    
    analyzer = StructureAnalyzer()
    results = analyzer.analyze_all(test_html)
    
    print("表格:")
    for table in results['tables']:
        print(f"  Headers: {table.headers}")
        print(f"  Rows: {table.rows}")
    
    print("\n列表:")
    for lst in results['lists']:
        print(f"  Items: {lst.items}")
    
    print("\nJSON 块:")
    for block in results['json_blocks']:
        print(f"  Data: {block.data}")
