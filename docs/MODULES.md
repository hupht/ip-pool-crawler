# 模块详细文档

本文档提供所有核心模块的 API 参考、使用示例和最佳实践。

## 📑 目录

### 核心爬虫模块
1. [DynamicCrawler](#1-dynamiccrawler) - 动态爬虫引擎
2. [UniversalParser](#2-universalparser) - 通用数据解析器
3. [StructureAnalyzer](#3-structureanalyzer) - HTML 结构分析
4. [PaginationDetector](#4-paginationdetector) - 分页检测
5. [PaginationController](#5-paginationcontroller) - 分页控制

### AI 模块
6. [LLMCaller](#6-llmcaller) - LLM API 调用
7. [LLMCache](#7-16-其他模块) - LLM 结果缓存
8. [LLMConfig](#7-16-其他模块) - LLM 配置管理
9. [ErrorHandler](#7-16-其他模块) - 智能错误处理

### 验证模块
10. [ProxyValidator](#7-16-其他模块) - 代理验证
11. [HTTPValidator](#7-16-其他模块) - HTTP 验证
12. [UniversalDetector](#7-16-其他模块) - 模式检测

### 传统模块
13. [Pipeline](#7-16-其他模块) - 传统爬虫流水线
14. [Storage](#7-16-其他模块) - 存储层
15. [Validator](#7-16-其他模块) - TCP 验证
16. [Checker](#7-16-其他模块) - 失败窗口管理

---

## 1. DynamicCrawler

### 📦 模块路径
```python
from crawler.dynamic_crawler import DynamicCrawler, DynamicCrawlResult
```

### 📖 类定义

#### DynamicCrawler

**初始化**：
```python
def __init__(self, settings: Settings):
    """
    参数:
        settings: 配置对象，包含数据库、LLM、爬虫等配置
    """
```

**主要方法**：

##### crawl()
```python
def crawl(
    self,
    url: str,
    max_pages: int = 1,
    use_ai: bool = False,
    no_store: bool = False,
    verbose: bool = False,
    render_js: bool = False,
) -> DynamicCrawlResult:
    """
    执行动态爬取
    
    参数:
        url: 起始URL
        max_pages: 最大爬取页数 (1-100)
        use_ai: 是否启用AI辅助
        no_store: 是否只测试不存储
        verbose: 是否输出详细日志
        render_js: 是否启用 Playwright 渲染后解析
        
    返回:
        DynamicCrawlResult 对象，包含统计信息
        
    异常:
        requests.RequestException: 网络请求失败
        Exception: 其他处理错误
    """
```

**关键内部能力（动态接口场景）**：
- `_discover_proxy_api_records(...)`
  - 在 HTML 与脚本中提取候选 API URL
  - 按白名单/黑名单过滤并探测 JSON 接口
- `_discover_runtime_api_records(...)`
  - 使用 Playwright 捕获运行时 `xhr/fetch` JSON 响应
  - 适配签名接口、动态 token 场景
- `crawler.js_fetcher.fetch_page_and_api_payloads_with_playwright(...)`
  - 同时返回渲染后 HTML 与捕获到的 JSON payload 列表
  - 支持 `max_payloads` 与 `max_response_bytes` 限制

**触发顺序**（简化）：
1. 常规 HTML 解析
2. 接口自动发现（`API_DISCOVERY_*`）
3. 运行时 sniff 回退（`RUNTIME_API_SNIFF_*`，且非 `render_js` 路径）

#### DynamicCrawlResult

**数据结构**：
```python
@dataclass
class DynamicCrawlResult:
    url: str                      # 起始URL
    pages_crawled: int            # 爬取页数
    extracted: int                # 提取总数
    valid: int                    # 有效数
    invalid: int                  # 无效数
    stored: int                   # 存储数
    session_id: Optional[int]     # 会话ID
```

### 📝 使用示例

#### 基础用法
```python
from crawler.runtime import load_settings
from crawler.dynamic_crawler import DynamicCrawler

# 加载配置
settings = load_settings(".env")

# 创建爬虫
crawler = DynamicCrawler(settings)

# 执行爬取
result = crawler.crawl(
    url="https://example.com/proxy",
    max_pages=5,
    verbose=True
)

print(f"爬取 {result.pages_crawled} 页")
print(f"提取 {result.extracted} 条")
print(f"有效 {result.valid} 条")
print(f"存储 {result.stored} 条")
```

#### AI 辅助模式
```python
result = crawler.crawl(
    url="https://complex-site.com/proxy",
    max_pages=3,
    use_ai=True,  # 启用 AI
    verbose=True
)

if result.session_id:
    # 查询AI调用日志
    conn = get_mysql_connection(settings)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM llm_call_logs WHERE session_id = %s",
            (result.session_id,)
        )
        logs = cur.fetchall()
        print(f"AI调用次数: {len(logs)}")
```

#### 测试模式
```python
result = crawler.crawl(
    url="https://unknown-site.com/proxy",
    max_pages=1,
    no_store=True,  # 不存储，只测试
    verbose=True
)

# 查看提取结果，决定是否正式爬取
if result.valid > 10:
    print("质量良好，可以正式爬取")
else:
    print("质量较差，考虑启用AI或放弃")
```

### 🎯 最佳实践

1. **首次测试**：使用 `no_store=True` 和 `max_pages=1`
2. **质量评估**：检查 `valid / extracted` 比率
3. **AI 策略**：质量差时启用 `use_ai=True`
4. **页数限制**：不确定时从小开始（3-5页）
5. **动态接口策略**：优先开启 `API_DISCOVERY_ENABLED`，签名站点再启用 `RUNTIME_API_SNIFF_ENABLED`

---

## 2. UniversalParser

### 📦 模块路径
```python
from crawler.universal_parser import UniversalParser, ProxyExtraction
```

### 📖 类定义

#### UniversalParser

**静态方法**：

##### parse()
```python
@staticmethod
def parse(
    html: Union[str, bytes],
    structure: Optional[Dict[str, Any]] = None,
    user_prompt: Optional[str] = None,
) -> List[ProxyExtraction]:
    """
    通用解析HTML
    
    参数:
        html: HTML内容（字符串或字节）
        structure: 预分析的结构（可选，自动调用StructureAnalyzer）
        user_prompt: 用户提示（保留，暂未使用）
        
    返回:
        ProxyExtraction 列表
    """
```

##### extract_all()
```python
@staticmethod
def extract_all(html: str) -> Tuple[List[ProxyExtraction], Dict[str, int]]:
    """
    完整提取流程（解析 + 统计）
    
    返回:
        (提取列表, 统计字典)
        
    统计字典示例:
        {
            "total": 100,
            "from_table": 80,
            "from_json": 10,
            "from_list": 5,
            "from_text": 5,
            "avg_confidence": 0.85
        }
    """
```

#### ProxyExtraction

**数据结构**：
```python
@dataclass
class ProxyExtraction:
    ip: str                               # IP地址
    port: Optional[int] = None            # 端口
    protocol: Optional[str] = None        # 协议
    source_type: str = "unknown"          # 来源类型
    confidence: float = 0.0               # 置信度
    raw_data: Optional[str] = None        # 原始数据
    additional_info: Dict[str, Any] = field(default_factory=dict)
```

### 📝 使用示例

#### 基础解析
```python
from crawler.universal_parser import UniversalParser

html = """
<table>
  <tr><th>IP</th><th>Port</th><th>Protocol</th></tr>
  <tr><td>1.2.3.4</td><td>8080</td><td>HTTP</td></tr>
  <tr><td>5.6.7.8</td><td>3128</td><td>HTTPS</td></tr>
</table>
"""

extractions = UniversalParser.parse(html)

for ext in extractions:
    print(f"{ext.ip}:{ext.port} ({ext.protocol})")
    print(f"  置信度: {ext.confidence:.2f}")
    print(f"  来源: {ext.source_type}")
```

#### 带统计信息
```python
extractions, stats = UniversalParser.extract_all(html)

print(f"总计: {stats['total']}")
print(f"表格: {stats['from_table']}")
print(f"JSON: {stats['from_json']}")
print(f"平均置信度: {stats['avg_confidence']:.2f}")
```

#### 过滤低置信度
```python
extractions = UniversalParser.parse(html)

high_quality = [
    ext for ext in extractions
    if ext.confidence >= 0.7
]

print(f"高质量数据: {len(high_quality)}/{len(extractions)}")
```

### 🎯 最佳实践

1. **置信度阈值**：建议 >= 0.5，严格场景 >= 0.7
2. **去重**：解析器已内置去重，无需额外处理
3. **错误处理**：解析失败返回空列表，不抛异常

---

## 3. StructureAnalyzer

### 📦 模块路径
```python
from crawler.structure_analyzer import StructureAnalyzer, Table, JSONBlock, HTMLList
```

### 📖 类定义

#### StructureAnalyzer

**类方法**：

##### analyze_all()
```python
@classmethod
def analyze_all(cls, html: str) -> Dict[str, Any]:
    """
    分析HTML中所有结构
    
    返回:
        {
            "tables": List[Table],
            "json_blocks": List[JSONBlock],
            "lists": List[HTMLList],
            "text_blocks": List[str]
        }
    """
```

##### find_tables()
```python
@classmethod
def find_tables(cls, html: str) -> List[Table]:
    """查找所有表格"""
```

##### find_json_blocks()
```python
@classmethod
def find_json_blocks(cls, html: str) -> List[JSONBlock]:
    """查找所有JSON块"""
```

##### guess_column_index()
```python
@classmethod
def guess_column_index(cls, headers: List[str], field: str) -> Optional[int]:
    """
    猜测列索引
    
    参数:
        headers: 表头列表 ["IP地址", "端口", "类型"]
        field: 字段名 "ip" / "port" / "protocol"
        
    返回:
        列索引（0-based）或 None
    """
```

### 📝 使用示例

#### 分析结构
```python
from crawler.structure_analyzer import StructureAnalyzer

html = open("proxy_page.html").read()

# 完整分析
structure = StructureAnalyzer.analyze_all(html)

print(f"找到 {len(structure['tables'])} 个表格")
print(f"找到 {len(structure['json_blocks'])} 个JSON块")
print(f"找到 {len(structure['lists'])} 个列表")

# 遍历表格
for table in structure['tables']:
    print(f"\n表格 (置信度: {table.confidence}):")
    print(f"  列: {', '.join(table.headers)}")
    print(f"  行数: {len(table.rows)}")
```

#### 智能列匹配
```python
headers = ["IP地址", "端口号", "协议类型", "国家"]

ip_col = StructureAnalyzer.guess_column_index(headers, "ip")
port_col = StructureAnalyzer.guess_column_index(headers, "port")

print(f"IP列索引: {ip_col}")      # 0
print(f"Port列索引: {port_col}")  # 1
```

### 🎯 最佳实践

1. **预分析优化**：先分析结构，再传给 UniversalParser
2. **置信度过滤**：忽略低于 0.6 的结构
3. **表格优先**：表格数据质量通常最高

---

## 4. PaginationDetector

### 📦 模块路径
```python
from crawler.pagination_detector import PaginationDetector, PaginationInfo, PaginationType
```

### 📖 类定义

#### PaginationDetector

**静态方法**：

##### detect_pagination()
```python
@staticmethod
def detect_pagination(html: str, base_url: str = '') -> PaginationInfo:
    """
    检测分页信息
    
    参数:
        html: HTML内容
        base_url: 当前页面URL（用于推断参数）
        
    返回:
        PaginationInfo 对象
    """
```

##### detect_url_pattern()
```python
@staticmethod
def detect_url_pattern(url: str) -> Optional[URLPattern]:
    """
    从URL推断分页模式
    
    示例:
        http://example.com/proxy?page=2
        推断: page参数, 当前值2, 下一页3
    """
```

### 📝 使用示例

#### 基础检测
```python
from crawler.pagination_detector import PaginationDetector

html = open("proxy_page.html").read()
current_url = "https://example.com/proxy?page=2"

info = PaginationDetector.detect_pagination(html, current_url)

if info.has_pagination:
    print(f"检测到分页: {info.pagination_type.value}")
    print(f"下一页: {info.next_page_url}")
    print(f"当前页: {info.current_page}")
    print(f"置信度: {info.confidence:.2f}")
else:
    print("未检测到分页")
```

####完整分页爬取
```python
def crawl_with_pagination(start_url: str, max_pages: int = 10):
    current_url = start_url
    page_num = 1
    
    while current_url and page_num <= max_pages:
        print(f"\n第 {page_num} 页: {current_url}")
        
        # 抓取页面
        html = fetch_page(current_url)
        
        # 提取数据
        proxies = UniversalParser.parse(html)
        print(f"  提取: {len(proxies)} 条")
        
        # 检测分页
        info = PaginationDetector.detect_pagination(html, current_url)
        
        if info.has_pagination and info.next_page_url:
            current_url = info.next_page_url
            page_num += 1
        else:
            print("  无下一页，停止")
            break
```

### 🎯 最佳实践

1. **置信度阈值**：>= 0.7 才继续翻页
2. **循环检测**：记录已访问URL，防止死循环
3. **URL推断优先**：传入 `base_url` 提高准确性

---

## 5. PaginationController

### 📦 模块路径
```python
from crawler.pagination_controller import PaginationController, PaginationState
```

### 📖 类定义

#### PaginationController

**初始化**：
```python
def __init__(self, max_pages: int = 10, max_pages_no_new_ip: int = 3):
    """
    参数:
        max_pages: 最大页数限制
        max_pages_no_new_ip: 连续无新IP停止阈值
    """
```

**方法**：

##### on_page_crawled()
```python
def on_page_crawled(self, new_ip_count: int) -> None:
    """
    记录页面爬取结果
    
    参数:
        new_ip_count: 本页新增IP数量
    """
```

##### should_continue()
```python
def should_continue(self) -> bool:
    """
    判断是否应继续爬取
    
    返回:
        True: 继续, False: 停止
    """
```

##### get_state()
```python
def get_state(self) -> PaginationState:
    """获取当前状态"""
```

### 📝 使用示例

```python
from crawler.pagination_controller import PaginationController

controller = PaginationController(
    max_pages=10,
    max_pages_no_new_ip=3
)

current_url = start_url
all_proxies = set()

while current_url and controller.should_continue():
    # 爬取页面
    html = fetch_page(current_url)
    proxies = UniversalParser.parse(html)
    
    # 去重统计
    before = len(all_proxies)
    all_proxies.update((p.ip, p.port) for p in proxies)
    new_count = len(all_proxies) - before
    
    # 更新控制器
    controller.on_page_crawled(new_count)
    
    print(f"第 {controller.get_state().current_page} 页:")
    print(f"  提取: {len(proxies)}")
    print(f"  新增: {new_count}")
    print(f"  连续无新: {controller.get_state().pages_no_new_ip}")
    
    # 检测下一页
    info = PaginationDetector.detect_pagination(html, current_url)
    current_url = info.next_page_url if info.has_pagination else None

print(f"\n停止原因: {controller.get_stop_reason()}")
```

### 🎯 最佳实践

1. **合理设置阈值**：`max_pages_no_new_ip=3` 较为平衡
2. **监控状态**：定期检查 `get_state()` 了解进度
3. **异常处理**：网络错误时也调用 `on_page_crawled(0)`

---

## 6. LLMCaller

### 📦 模块路径
```python
from crawler.llm_caller import LLMCaller
from crawler.llm_config import LLMConfig
```

### 📖 类定义

#### LLMCaller

**初始化**：
```python
def __init__(self, config: LLMConfig):
    """
    参数:
        config: LLM配置对象
    """
```

**方法**：

##### call_llm_for_parsing()
```python
def call_llm_for_parsing(
    self,
    html: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    调用LLM解析HTML
    
    参数:
        html: HTML内容
        context: 上下文信息（可选）
        
    返回:
        {
            "proxies": [...],
            "cost_usd": 0.0003,
            "tokens": {"input": 1200, "output": 150},
            "cached": False
        }
    """
```

##### estimate_cost()
```python
def estimate_cost(self, input_tokens: int, output_tokens: int = 0) -> float:
    """
    估算成本
    
    返回:
        成本（美元）
    """
```

### 📝 使用示例

#### 基础调用
```python
from crawler.llm_config import LLMConfig
from crawler.llm_caller import LLMCaller

# 加载配置
config = LLMConfig.from_env()

# 创建调用器
caller = LLMCaller(config)

# 调用LLM
html = open("complex_page.html").read()
result = caller.call_llm_for_parsing(html)

if "error" not in result:
    print(f"提取: {len(result['proxies'])} 条")
    print(f"成本: ${result['cost_usd']:.6f}")
    print(f"Tokens: {result['tokens']}")
else:
    print(f"错误: {result['error']}")
```

#### 成本预估
```python
# 当 LLM_SUBMIT_FULL_HTML=false 时，按配置截取
snippet_chars = config.html_snippet_chars
html_snippet = html[:snippet_chars]
estimated_tokens = len(html_snippet) // 4
estimated_cost = caller.estimate_cost(estimated_tokens, 100)

print(f"预估tokens: {estimated_tokens}")
print(f"预估成本: ${estimated_cost:.6f}")

if estimated_cost < 0.01:  # 1美分以下
    result = caller.call_llm_for_parsing(html)
```

### 🎯 最佳实践

1. **成本预估**：调用前先估算
2. **错误处理**：检查返回中的 `error` 字段
3. **HTML提交策略**：使用 `.env` 配置 `LLM_SUBMIT_FULL_HTML/LLM_HTML_SNIPPET_CHARS`
4. **重试机制**：已内置重试，无需手动重试

---

## 7-16. 其他模块

由于篇幅限制，其他模块的详细文档请参考：

- **LLMCache**: 见 [LLM_INTEGRATION.md](./LLM_INTEGRATION.md)
- **ErrorHandler**: 见 [LLM_INTEGRATION.md](./LLM_INTEGRATION.md)
- **ProxyValidator**: 见 [FEATURES.md](./FEATURES.md#5-多层验证系统)
- **HTTPValidator**: 见 [FEATURES.md](./FEATURES.md)
- **Pipeline**: 见 [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Storage**: 见 [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## 🔧 集成示例

### 完整动态爬虫流程

```python
from crawler.runtime import load_settings
from crawler.dynamic_crawler import DynamicCrawler
from crawler.storage import get_mysql_connection

# 1. 加载配置
settings = load_settings(".env")

# 2. 创建爬虫
crawler = DynamicCrawler(settings)

# 3. 执行爬取
result = crawler.crawl(
    url="https://example.com/proxy",
    max_pages=5,
    use_ai=False,
    verbose=True
)

# 4. 输出结果
print(f"""
爬取完成
━━━━━━━━━━━━━━━━━━━━━━
  页数: {result.pages_crawled}
  提取: {result.extracted}
  有效: {result.valid}
  存储: {result.stored}
""")

# 5. 查询数据库
if result.session_id:
    conn = get_mysql_connection(settings)
    with conn.cursor() as cur:
        # 查询会话详情
        cur.execute(
            "SELECT * FROM crawl_sessions WHERE session_id = %s",
            (result.session_id,)
        )
        session = cur.fetchone()
        print(f"会话状态: {session['status']}")
        
        # 查询页面日志
        cur.execute(
            "SELECT * FROM page_logs WHERE session_id = %s",
            (result.session_id,)
        )
        pages = cur.fetchall()
        print(f"页面日志: {len(pages)} 条")
```

### 自定义解析流程

```python
from crawler.structure_analyzer import StructureAnalyzer
from crawler.universal_parser import UniversalParser
from crawler.proxy_validator import ProxyValidator

# 1. 分析结构
html = fetch_page(url)
structure = StructureAnalyzer.analyze_all(html)

# 2. 过滤高质量结构
good_tables = [
    table for table in structure['tables']
    if table.confidence >= 0.8
]

# 3. 手动提取
extractions = []
for table in good_tables:
    extracted = UniversalParser.extract_from_tables([table])
    extractions.extend(extracted)

# 4. 验证
validator = ProxyValidator()
valid_proxies = []

for ext in extractions:
    proxy = {
        "ip": ext.ip,
        "port": ext.port,
        "protocol": ext.protocol or "http"
    }
    
    result = validator.validate_proxy(proxy)
    
    if result.is_valid:
        valid_proxies.append(proxy)
    else:
        print(f"无效: {proxy} - {result.anomalies}")

# 5. 存储
# ... (使用 Storage 模块)
```

---

**相关文档**：
- 👉 [架构设计](./ARCHITECTURE.md)
- 👉 [功能详解](./FEATURES.md)
- 👉 [API 集成](./UNIVERSAL_CRAWLER_API.md)
- 👉 [LLM 集成](./LLM_INTEGRATION.md)
