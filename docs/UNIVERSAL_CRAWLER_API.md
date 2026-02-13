# 通用动态爬虫 - API 文档

**版本**：1.0  
**日期**：2026-02-12

---

## 📚 目录

1. [核心模块](#核心模块)
2. [数据结构](#数据结构)
3. [主要类和方法](#主要类和方法)
4. [使用示例](#使用示例)

---

## 核心模块

> 注：本节以当前仓库中的实际实现为准。

### `crawler.llm_config`
LLM 配置管理

### `crawler.universal_detector`
IP 和端口特征检测

### `crawler.structure_analyzer`
页面结构识别

### `crawler.universal_parser`
通用数据解析

### `crawler.pagination_detector`
分页检测

### `crawler.pagination_controller`
分页流程控制

### `crawler.proxy_validator`
数据验证和异常检测

### `crawler.http_validator`
HTTP/TCP 连通性验证

### `crawler.llm_caller`
LLM API 调用

### `crawler.llm_cache`
LLM 结果缓存

### `crawler.error_handler`
三层容错协调

### `crawler.dynamic_crawler`
主控制器

---

## 数据结构

### `IPMatch`
```python
@dataclass
class IPMatch:
    ip: str                  # IP 地址
    port: Optional[int]      # 端口（可选）
    protocol: Optional[str]  # 协议 (http/https/socks5 等)
    matched_text: str        # 原始匹配文本
    position: Tuple[int, int]  # 位置 (start, end)
    context: str             # 周边上下文
    confidence: float        # 置信度 0-1
    source: str              # 数据来源 (regex/table/json/html_list)
```

### `ProxyRecord`
```python
@dataclass
class ProxyRecord:
    ip: str
    port: int
    protocol: str = 'http'
    anonymity: Optional[str] = None
    country: Optional[str] = None
    extraction_method: str = 'heuristic'
    confidence: float = 0.5
    page_number: int = 1
    source_url: str = ''
```

### `DynamicCrawlResult`
```python
@dataclass
class DynamicCrawlResult:
    url: str
    pages_crawled: int
    extracted: int
    valid: int
    invalid: int
    stored: int
```

---

## 主要类和方法

### UniversalDetector

```python
class UniversalDetector:
    """IP 和端口特征检测"""
    
    @staticmethod
    def detect_ips(html: str) -> List[str]:
        """
        检测 HTML 中的所有 IP 地址
        
        Args:
            html: HTML 内容
            
        Returns:
            IP 地址列表
        """
        
    @staticmethod
    def detect_ip_port_pairs(html: str) -> List[Tuple[str, int]]:
        """
        检测 HTML 中的 IP:PORT 对
        
        Args:
            html: HTML 内容
            
        Returns:
            (IP, PORT) 元组列表
        """
        
    @staticmethod
    def detect_protocols(html: str) -> List[str]:
        """
        检测 HTML 中的协议字段
        
        Args:
            html: HTML 内容
            
        Returns:
            协议列表 (http, https, socks5 等)
        """
```

### StructureAnalyzer

```python
class StructureAnalyzer:
    """页面结构识别"""
    
    @staticmethod
    def find_tables(html: str) -> List[dict]:
        """
        查找所有表格
        
        Returns:
            表格列表，每个表格包含:
            {
                'headers': ['IP', '端口', '协议'],
                'rows': [['1.2.3.4', 8080, 'http'], ...],
                'position': (start, end)
            }
        """
        
    @staticmethod
    def find_lists(html: str) -> List[dict]:
        """查找所有列表结构"""
        
    @staticmethod
    def find_json_blocks(html: str) -> List[dict]:
        """查找 JSON 数据块"""
```

### UniversalParser

```python
class UniversalParser:
    """通用数据解析"""
    
    def parse(
        self, 
        html: str,
        structure: Optional[dict] = None,
        user_hint: Optional[str] = None
    ) -> List[ProxyRecord]:
        """
        解析 HTML 并提取代理信息
        
        Args:
            html: HTML 内容
            structure: 页面结构（由 StructureAnalyzer 提供）
            user_hint: 用户提示（如 "IP 在第一列"）
            
        Returns:
            代理记录列表，每条包含 confidence
        """
        
    @staticmethod
    def calculate_confidence(
        extraction_source: str,
        field_presence: dict,
        context_certainty: float,
        format_validity: bool
    ) -> float:
        """计算置信度 (0-1)"""
```

### PaginationDetector

```python
class PaginationDetector:
    """分页检测"""
    
    @staticmethod
    def detect_url_pattern(url: str) -> Optional[dict]:
        """
        检测 URL 中的分页参数模式
        
        Returns:
            {
                'pattern': 'page',      # 参数名
                'current_value': 1,
                'next_url': '...?page=2'
            }
        """
        
    @staticmethod
    def find_next_link(html: str) -> Optional[str]:
        """检测下一页链接"""
        
    @staticmethod
    def find_load_more_button(html: str) -> Optional[dict]:
        """检测加载更多按钮"""
```

### PaginationController

```python
class PaginationController:
    """分页流程控制"""
    
    def __init__(self, max_pages: int = 5, max_pages_no_new_ip: int = 3):
        """初始化"""
        
    def should_continue(self) -> bool:
        """判断是否继续爬取"""

    def mark_visited(self, url: str) -> bool:
        """标记 URL 已访问；重复 URL 返回 False"""
        
    def get_next_url(self, current_url: str, detected_next_url: Optional[str]) -> Optional[str]:
        """获取下一页 URL"""
        
    def record_page_ips(self, ip_count: int) -> None:
        """记录当前页 IP 数"""
        
    def get_stats(self) -> dict:
        """获取统计信息"""
```

### ProxyValidator

```python
class ProxyValidator:
    """数据验证和异常检测"""
    
    @staticmethod
    def validate_ip(ip: str) -> ValidationResult:
        """验证 IP 格式和范围"""
        
    @staticmethod
    def validate_port(port: Optional[int]) -> ValidationResult:
        """验证端口范围 (1-65535)"""
        
    @staticmethod
    def validate_proxy(
        ip: str,
        port: Optional[int] = None,
        protocol: Optional[str] = None
    ) -> ValidationResult:
        """验证完整代理记录"""
```

### LLMCaller

```python
class LLMCaller:
    """LLM API 调用"""
    
    def __init__(self, config: LLMConfig):
        """初始化"""
        
    def call_llm_for_parsing(
        self,
        html: str,
        context: Optional[dict] = None
    ) -> dict:
        """
        调用 LLM 解析 HTML
        
        Returns:
            {
                'proxies': [
                    {
                        'ip': '1.2.3.4',
                        'port': 8080,
                        'protocol': 'http',
                        'confidence': 0.95,
                        'reasoning': '...'
                    }
                ]
            }
        """
        
    def estimate_cost(self, input_tokens: int, output_tokens: int = 0) -> float:
        """按 token 估算 API 调用成本（美元）"""
```

### ErrorHandler

```python
class ErrorHandler:
    """三层容错协调"""
    
    def process_page(
        self,
        html: str,
        context: Optional[dict] = None
    ) -> Tuple[List[dict], List[dict]]:
        """
        处理单页爬取
        
        Args:
            html: HTML 内容
            context: 页面上下文
            
        Returns:
            (验证通过的数据, 待审查的数据)
        """
        
    def should_use_ai(self, reason: str) -> bool:
        """判断是否调用 AI"""
```

### DynamicCrawler

```python
class DynamicCrawler:
    """主控制器"""
    
    def crawl(
        self,
        url: str,
        max_pages: int = 1,
        use_ai: bool = False,
        no_store: bool = False,
        verbose: bool = False,
    ) -> DynamicCrawlResult:
        """
        爬取指定 URL
        
        Args:
            url: 起始 URL
            max_pages: 最大页数
            use_ai: 是否启用 AI（当前版本预留）
            no_store: 是否跳过 MySQL 写入
            verbose: 是否打印详细日志
            
        Returns:
            爬取结果
        """
```

---

## 使用示例

### 例子 1：最简单的用法

```python
from crawler.dynamic_crawler import DynamicCrawler
from crawler.runtime import load_settings

settings = load_settings()
crawler = DynamicCrawler(settings)
result = crawler.crawl('https://example.com/proxy')

print(f"抓取页数：{result.pages_crawled}")
print(f"提取数量：{result.extracted}")
```

### 例子 2：自定义配置

```python
from crawler.dynamic_crawler import DynamicCrawler
from crawler.runtime import load_settings

settings = load_settings()
crawler = DynamicCrawler(settings)
result = crawler.crawl(
    'https://example.com/proxy',
    max_pages=10,
    use_ai=True,
    no_store=True,
    verbose=True,
)
```

### 例子 3：检查爬取结果

```python
from crawler.dynamic_crawler import DynamicCrawler
from crawler.runtime import load_settings

settings = load_settings()
crawler = DynamicCrawler(settings)
result = crawler.crawl('https://example.com/proxy')

# 访问爬取统计
print(f"页数：{result.pages_crawled}")
print(f"提取：{result.extracted}")
print(f"有效：{result.valid}")
print(f"无效：{result.invalid}")
print(f"入库：{result.stored}")
```

### 例子 4：手动分页控制

```python
from crawler.pagination_detector import PaginationDetector
from crawler.pagination_controller import PaginationController
from crawler.fetcher import fetch

url = 'https://example.com/proxy?page=1'
controller = PaginationController(max_pages=5)

while controller.should_continue():
    if not controller.mark_visited(url):
        break

    # 获取当前页
    html = fetch(url)
    
    # 处理页面
    ips = extract_ips(html)
    controller.record_page_ips(len(ips))
    
    # 找下一页
    detected_next_url = PaginationDetector.find_next_link(html)
    next_url = controller.get_next_url(url, detected_next_url)
    if next_url:
        url = next_url
    else:
        break
```

---

## 高级用法

### 自定义 LLM 提示词

```python
from crawler.llm_caller import LLMCaller

class CustomLLMCaller(LLMCaller):
    def _build_prompt(self, html: str, context: dict) -> str:
        return f"""
        分析以下 HTML 页面，重点查找代理 IP 和端口。
        优先查找表格格式的数据。
        
        HTML: {html[:3000]}
        
        返回 JSON 格式。
        """
```

### 自定义数据验证

```python
from crawler.proxy_validator import ProxyValidator

class CustomValidator(ProxyValidator):
    @staticmethod
    def validate_proxy(ip: str, port: int) -> bool:
        # 自定义验证逻辑
        if ProxyValidator.validate_ip(ip).is_valid and ProxyValidator.validate_port(port).is_valid:
            # 额外检查
            if ip.startswith('192.168.'):
                return False  # 不接受私网 IP
            return True
        return False
```

---

## 错误处理

所有 API 可能抛出以下异常：

```python
class CrawlException(Exception):
    """爬取异常基类"""
    pass

class NetworkException(CrawlException):
    """网络错误"""
    pass

class ParseException(CrawlException):
    """解析错误"""
    pass

class ValidateException(CrawlException):
    """验证错误"""
    pass

class LLMException(CrawlException):
    """LLM API 错误"""
    pass
```

使用示例：

```python
from crawler.dynamic_crawler import DynamicCrawler
from crawler.exceptions import CrawlException

try:
    result = crawler.crawl('https://example.com/proxy')
except CrawlException as e:
    print(f"爬取失败：{e}")
```

---

## 性能提示

1. **启用缓存**：`AI_CACHE_ENABLED=true` 避免重复请求
2. **调整并发**：`SOURCE_WORKERS=4` 但不要过高
3. **设置超时**：`PAGE_FETCH_TIMEOUT_SECONDS=10` 防止卡住
4. **成本控制**：`AI_COST_LIMIT_USD=50` 限制支出

---

## 📞 相关资源

- [配置指南](./UNIVERSAL_CRAWLER_CONFIG.md)
- [使用指南](./UNIVERSAL_CRAWLER_USAGE.md)
- [LLM 集成](./LLM_INTEGRATION.md)
- [源代码](../crawler/)
