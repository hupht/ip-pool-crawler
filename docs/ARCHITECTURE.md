# 架构设计

本文档介绍 IP Pool Crawler 的系统架构、核心模块和数据流。

## 📖 目录

- [系统架构概览](#-系统架构概览)
  - [整体架构图](#整体架构图)
  - [双引擎对比](#双引擎对比)
  - [架构设计原则](#架构设计原则)
- [核心模块详解](#-核心模块详解)
  - [传统爬虫模块](#传统爬虫模块-1-9)
  - [动态爬虫模块](#-新增核心模块详解-10-21)
- [数据流详解](#-数据流详解)
  - [传统爬虫流程](#流程-1-传统爬虫单次爬取-run_once)
  - [动态爬虫流程](#流程-2-动态爬虫爬取-crawl-custom)
  - [获取代理流程](#流程-3-获取代理-get-proxy)
  - [批量检查流程](#流程-4-批量检查-check)
- [配置参数详解](#️-配置参数详解)
- [数据库设计](#️-数据库设计)
- [性能优化](#-性能优化)
- [关键设计决策](#-关键设计决策)
- [故障排查指南](#️-故障排查指南)
- [扩展性设计](#-扩展性设计)
- [总结](#-总结)

---

## 🏗️ 系统架构概览

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI 入口 (cli.py)                             │
├─────────────────────────────────────────────────────────────────────┤
│  传统命令                    │  🆕 新增命令                          │
│  ├── run                     │  ├── crawl-custom (动态爬虫)          │
│  ├── check                   │  ├── diagnose-* (诊断工具)           │
│  ├── get-proxy               │  └── verify-* (验证工具)             │
│  └── ...                     │                                      │
├─────────────────────────────────────────────────────────────────────┤
│                         双引擎架构                                   │
│  ┌──────────────────────┐          ┌────────────────────────────┐  │
│  │  传统爬虫引擎         │          │  🆕 动态爬虫引擎            │  │
│  │  (Pipeline)           │          │  (DynamicCrawler)          │  │
│  │                       │          │                            │  │
│  │  预设源 → 解析        │          │  通用解析 → AI辅助         │  │
│  │  ↓                    │          │  ↓                         │  │
│  │  固定格式             │          │  自适应格式                │  │
│  └──────────────────────┘          └────────────────────────────┘  │
│                                                                      │
│                    共享核心组件层                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  验证层: ProxyValidator + HTTPValidator + Validator          │   │
│  │  存储层: Storage (MySQL + Redis)                             │   │
│  │  日志层: AuditLogger                                         │   │
│  │  配置层: Settings                                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│              🆕 智能解析组件（AI驱动）                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  UniversalParser → StructureAnalyzer                         │   │
│  │        ↓               ↓                                     │   │
│  │  ErrorHandler → LLMCaller → LLMCache                         │   │
│  │        ↓               ↓                                     │   │
│  │  PaginationDetector → PaginationController                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│              存储层 (MySQL + Redis)                                  │
│  ├── MySQL: 历史库 (proxy_ips, audit_logs, crawl_sessions等)       │
│  └── Redis: 快速池 (内存、高速访问)                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 双引擎对比

| 特性 | 传统爬虫 (Pipeline) | 动态爬虫 (DynamicCrawler) |
|-----|-------------------|-------------------------|
| **数据源** | 预定义源列表 | 任意 URL |
| **解析方式** | 固定解析器（需开发） | 通用解析器（自适应） |
| **分页支持** | 手动实现 | 自动检测和跟踪 |
| **AI 辅助** | ❌ 不支持 | ✅ 可选启用 |
| **会话跟踪** | ❌ 无 | ✅ 完整 session 记录 |
| **审核队列** | ❌ 无 | ✅ 低置信度数据进队列 |
| **成本控制** | ❌ 不适用 | ✅ 可限制 AI 成本 |
| **适用场景** | 稳定、已知的代理源 | 探索新源、复杂页面 |
| **开发成本** | 高（每个源需适配） | 低（无需定制开发） |
| **运行成本** | 极低 | 中（AI 可选） |
| **准确率** | 高（针对性解析） | 中-高（通用解析） |

### 架构设计原则

1. **分层解耦**：CLI → 引擎 → 核心组件 → 存储，各层独立可替换
2. **双引擎并存**：传统爬虫保证稳定性，动态爬虫提供扩展性
3. **渐进式AI**：默认不依赖AI，遇到复杂情况才调用（ErrorHandler 智能判断）
4. **成本可控**：LLM 调用有预算上限、缓存机制、降级策略
5. **可观测性**：全流程审计日志，记录所有关键操作和性能指标
6. **容错设计**：单个源/页面失败不影响整体，软删除支持恢复

## 📁 核心模块详解

### 1. Pipeline (`crawler/pipeline.py`)

**职责**：协调整个爬取流程

**主要函数**：
- `run_once(settings)` - 单次完整爬取
  1. 加载数据源
  2. 并发抓取 + 解析
  3. 写入 MySQL
  4. 并发 TCP 验证
  5. 计算评分
  6. 写入 Redis

**关键特性**：
- 使用 `ThreadPoolExecutor` 实现并发
- 2 个线程池：一个用于抓取，一个用于验证
- 异常处理完善，单个源失败不影响其他源

### 2. Fetcher (`crawler/fetcher.py`)

**职责**：HTTP 请求，获取代理源原始数据

**主要函数**：
- `fetch_source(source, settings)` - 抓取单个源
  - 支持重试机制
  - 可配置超时时间
  - 返回 (raw_content, status_code)

**配置参数**：
- `HTTP_TIMEOUT` - 单个请求超时（秒）
- `HTTP_RETRIES` - 失败重试次数
- `USER_AGENT` - User-Agent 字符串

### 3. Parsers (`crawler/parsers.py`)

**职责**：解析不同格式的代理列表

**支持的格式**：
- JSON 格式 (Geonode)
- 纯文本格式 (proxy-list-download)
- HTML 格式 (免费代理网站)

**主要函数**：
- `parse_geonode(raw)` - 解析 JSON
- `parse_proxy_list_download_http(raw)` - 解析文本
- 等...

**输出**：统一的代理列表格式
```python
[
  {
    "ip": "192.168.1.1",
    "port": 8080,
    "protocol": "http",
    "country": "US",
    "anonymity": "elite"
  },
  ...
]
```

### 4. Validator (`crawler/validator.py`)

**职责**：验证代理可用性，计算评分

**主要函数**：
- `tcp_check(ip, port, timeout)` - TCP 连接测试
  - 返回 (success: bool, latency_ms: int)
  
- `score_proxy(latency_ms, source_count)` - 计算评分
  - 依赖：延迟、来源数量
  - 范围：0-100，越高越好

**验证策略**：
- 使用 socket 进行 TCP 连接
- 测试连接是否可建立
- 不实际发送 HTTP 请求（快速验证）

### 5. Storage (`crawler/storage.py`)

**职责**：MySQL 和 Redis 的读写操作

**主要函数**：

**MySQL 操作**：
- `upsert_source()` - 插入/更新数据源
- `upsert_proxy()` - 插入/更新代理
- `update_proxy_check()` - 记录验证结果
- `fetch_check_batch()` - 获取待验证代理

**Redis 操作**：
- `upsert_redis_pool()` - 更新 Redis 代理池

**自动初始化**：
- 检测到数据库/表不存在时自动创建
- 加载 `sql/schema.sql` 执行初始化

### 6. ProxyPicker (`crawler/proxy_picker.py`)

**职责**：从池中选取代理

**选取策略**：
1. 优先从 Redis 快速池获取
2. Redis 为空则从 MySQL 回退
3. 支持按协议、国家过滤
4. 支持随机或有序选取

**主要函数**：
- `pick_proxies(count, protocol, country)` - 选取代理

### 7. Checker (`crawler/checker.py`)

**职责**：失败窗口管理，决定代理生死

**失败窗口机制**：
- 记录代理首次失败时间
- 失败次数达到阈值后标记为 `is_alive=0`（软删除）
- 失败窗口过期后恢复（重新检验）

**配置参数**：
- `FAIL_WINDOW_HOURS` - 失败窗口时长（小时）
- `FAIL_THRESHOLD` - 失败次数阈值
- `CHECK_RETRY_DELAY` - 重试延迟（秒）

**状态转移**：
```
健康 (is_alive=1)
  ↓ 首次验证失败
失败中 (fail_count=1, fail_window_start记录时间)
  ↓ 继续失败 fail_count达到阈值
标记删除 (is_alive=0)
  ↓ 窗口过期
重新验证 (fail_count清零, 重新激活)
```

### 8. Config (`crawler/config.py`)

**职责**：管理配置，加载 `.env` 文件

**主要内容**：
- `Settings` dataclass - 配置数据
- `Settings.from_env()` - 从环境变量加载
- 提供配置默认值

**配置分类**：
- **MySQL 配置**
- **Redis 配置**
- **HTTP 配置**（超时、重试）
- **并发配置**（工作线程数）
- **检查配置**（失败窗口、重试）
- **日志配置**（新增）

### 9. Logging (`crawler/logging/`)

**职责**：审计日志系统

**模块组成**：
- `logger.py` - `AuditLogger` 类，记录各类操作
- `formatters.py` - 格式化和脱敏
- `__init__.py` - 模块入口

**记录的操作**：
- 数据库操作（INSERT/UPDATE/DELETE）
- HTTP 请求（URL、状态、延迟）
- TCP 检查（IP、端口、结果）
- 流程事件（爬虫启动、完成、错误）

**脱敏机制**：
- IP 地址：`192.168.1.100` → `192.168.1.***`
- 密码：`secret` → `***`
- Token、API Key 等敏感信息自动脱敏

---

## 🆕 新增核心模块详解

### 10. DynamicCrawler (`crawler/dynamic_crawler.py`)

**职责**：通用动态爬虫，可自动爬取任意代理网站

**核心功能**：
- 自动检测页面结构（表格、JSON、列表）
- 智能分页检测和控制
- AI 辅助解析复杂页面
- 多层验证和评分
- 完整会话跟踪

**主要函数**：
- `crawl(url, max_pages, use_ai, no_store)` - 执行爬取
  - 返回 `DynamicCrawlResult` 包含统计信息
  - 支持最多100页递归爬取
  - 智能停止策略（连续N页无新IP）

**工作流程**：
```
URL → 抓取页面 → 通用解析 → 分页检测
  ↓        ↓          ↓         ↓
HTML   ErrorHandler  去重   生成下一页URL
  ↓        ↓          ↓         ↓
AI辅助   验证代理   存储    继续/停止
```

**特性**：
- 会话管理：记录 `crawl_sessions` 表
- 页面日志：记录 `page_logs` 表
- 审核队列：低置信度数据进 `review_queue`
- 支持导出 JSON/CSV 格式

### 11. UniversalParser (`crawler/universal_parser.py`)

**职责**：通用数据解析器，从各种格式中提取代理

**支持的格式**：
- HTML 表格（自动识别列）
- JSON 数据块
- 无序/有序列表
- 纯文本（正则提取）

**核心流程**：
```python
html → StructureAnalyzer.analyze_all()
  ↓
{tables: [...], json_blocks: [...], lists: [...], text_blocks: [...]}
  ↓
extract_from_tables() + extract_from_json() + ...
  ↓
[ProxyExtraction, ProxyExtraction, ...]
  ↓
deduplicate_proxies()
```

**ProxyExtraction 数据结构**：
- `ip` - IP 地址
- `port` - 端口
- `protocol` - 协议
- `confidence` - 置信度 (0.0-1.0)
- `source_type` - 数据源类型
- `additional_info` - 额外信息

**智能列名匹配**：
- `ip`: ['ip', 'ip地址', 'ip address', 'host']
- `port`: ['port', '端口', 'port号']
- `protocol`: ['protocol', '协议', 'type']

### 12. StructureAnalyzer (`crawler/structure_analyzer.py`)

**职责**：分析 HTML 结构，识别数据容器

**核心功能**：
- `find_tables(html)` - 提取所有表格
- `find_json_blocks(html)` - 查找 JSON 数据
- `find_lists(html)` - 识别列表结构
- `guess_column_index(headers, field)` - 智能列匹配

**Table 结构**：
```python
@dataclass
class Table:
    headers: List[str]          # 列标题
    rows: List[List[str]]       # 行数据
    footers: List[str]          # 页脚
    confidence: float           # 置信度
```

**JSONBlock 结构**：
```python
@dataclass
class JSONBlock:
    data: Dict[str, Any]        # 解析后的JSON
    raw_text: str               # 原始文本
    confidence: float = 0.95
```

**HTMLList 结构**：
```python
@dataclass
class HTMLList:
    items: List[str]            # 列表项
    list_type: str = "ul"       # ul/ol/div
    confidence: float = 0.8
```

### 13. PaginationDetector (`crawler/pagination_detector.py`)

**职责**：自动检测网页分页模式

**支持的分页类型**：
```python
class PaginationType(Enum):
    PARAMETER_BASED = "parameter_based"    # ?page=1
    OFFSET_BASED = "offset_based"          # ?offset=0
    CURSOR_BASED = "cursor_based"          # ?cursor=abc
    AJAX_BASED = "ajax_based"              # AJAX加载
    REL_PAGINATION = "rel_pagination"      # <link rel="next">
```

**检测策略**（优先级从高到低）：
1. **URL 参数推断** - 分析当前 URL 中的分页参数
2. **rel 标签检测** - 查找 `<link rel="next">` 或 `<a rel="next">`
3. **下一页链接检测** - 匹配常见"下一页"文本
4. **数字链接检测** - 识别页码链接（1, 2, 3...）

**PaginationInfo 结构**：
```python
@dataclass
class PaginationInfo:
    has_pagination: bool
    pagination_type: PaginationType
    next_page_url: str
    current_page: int
    total_pages: int
    confidence: float
    detection_method: str
```

**常见模式**：
- 参数名：`page`, `p`, `pagenum`, `offset`, `start`
- 下一页文本：`下一页`, `next`, `more`, `继续`

### 14. PaginationController (`crawler/pagination_controller.py`)

**职责**：控制分页爬取流程

**核心功能**：
- 限制最大页数
- 检测连续无新IP情况
- 自动停止策略

**状态管理**：
```python
@dataclass
class PaginationState:
    current_page: int
    pages_crawled: int
    total_proxies_found: int
    pages_no_new_ip: int
    should_continue: bool
```

**停止条件**：
1. 达到最大页数限制
2. 连续 N 页无新 IP（可配置）
3. 检测到分页循环

**主要函数**：
- `on_page_crawled(new_ip_count)` - 记录爬取结果
- `should_continue()` - 判断是否继续

### 15. LLMCaller (`crawler/llm_caller.py`)

**职责**：调用 LLM API 进行智能解析

**支持的模型**：
- `gpt-4o-mini` - 快速、便宜（推荐）
- `gpt-4-turbo` - 精确、昂贵
- `gpt-3.5-turbo` - 较旧版本

**成本估算**（每1K tokens）：
```python
MODEL_PRICING_PER_1K_TOKENS = {
    "gpt-4o-mini": {
        "input": 0.00015,
        "output": 0.00060
    },
    "gpt-4-turbo": {
        "input": 0.01,
        "output": 0.03
    }
}
```

**主要函数**：
- `call_llm_for_parsing(html, context)` - 调用LLM解析
- `parse_llm_response(response)` - 解析LLM返回
- `estimate_cost(input_tokens, output_tokens)` - 估算成本

**返回格式**：
```json
{
  "proxies": [
    {
      "ip": "1.2.3.4",
      "port": 8080,
      "protocol": "http",
      "confidence": 0.9
    }
  ],
  "cost_usd": 0.0003,
  "tokens": {
    "input": 1200,
    "output": 150
  }
}
```

### 16. LLMCache (`crawler/llm_cache.py`)

**职责**：缓存 LLM 调用结果，减少API成本

**缓存策略**：
- LRU（最近最少使用）策略
- 基于 HTML + context 的哈希键
- 可配置 TTL（生存时间）

**主要函数**：
- `get(cache_key)` - 获取缓存
- `set(cache_key, value)` - 设置缓存
- `build_cache_key(html, context)` - 生成缓存键
- `cleanup_expired()` - 清理过期缓存

**缓存键生成**：
```python
cache_key = hashlib.sha256(
    (html[:2000] + json.dumps(context, sort_keys=True))
    .encode('utf-8')
).hexdigest()
```

### 17. LLMConfig (`crawler/llm_config.py`)

**职责**：LLM 配置管理

**配置项**：
```python
@dataclass
class LLMConfig:
    enabled: bool                      # 是否启用LLM
    api_key: str                       # API密钥
    base_url: str                      # API地址
    model: str                         # 模型名称
    max_retries: int                   # 最大重试次数
    cost_limit_usd: float              # 成本上限（美元）
    
    # 触发条件
    trigger_on_low_confidence: bool    # 低置信度时触发
    trigger_on_no_table: bool          # 无表格时触发
    trigger_on_failed_parse: bool      # 解析失败时触发
    trigger_on_user_request: bool      # 用户请求时触发
    
    # 缓存配置
    cache_enabled: bool                # 启用缓存
    cache_ttl_hours: int               # 缓存TTL（小时）
```

**从环境变量加载**：
```python
config = LLMConfig.from_env()
```

### 18. ErrorHandler (`crawler/error_handler.py`)

**职责**：智能错误处理和AI降级策略

**核心功能**：
- 检测解析失败原因
- 判断是否需要AI辅助
- 管理AI调用成本
- 协调多个组件

**工作流程**：
```
解析失败 → should_use_ai(reason)?
  ↓ Yes              ↓ No
can_afford?        返回空结果
  ↓ Yes
check_cache?
  ↓ Miss
call_llm_for_parsing()
  ↓
cache_result
  ↓
return proxies
```

**主要函数**：
- `should_use_ai(reason)` - 判断是否使用AI
- `handle_extraction_failure(html, context)` - 处理解析失败
- `process_page(html, context)` - 完整处理流程

**失败原因**：
- `low_confidence` - 低置信度
- `no_table` - 无表格结构
- `failed_parse` - 解析失败
- `user_request` - 用户明确要求

### 19. ProxyValidator (`crawler/proxy_validator.py`)

**职责**：代理数据验证和异常检测

**验证层次**：
1. **格式验证** - IP地址格式、端口范围
2. **语义验证** - 私网IP、保留地址、广播地址
3. **安全验证** - 可疑端口、已知恶意IP
4. **重复检测** - 去重

**异常类型**：
```python
class AnomalyType(Enum):
    PRIVATE_IP = "private_ip"
    RESERVED_IP = "reserved_ip"
    BROADCAST_IP = "broadcast_ip"
    INVALID_IP = "invalid_ip"
    INVALID_PORT = "invalid_port"
    MISSING_PORT = "missing_port"
    UNSUPPORTED_PROTOCOL = "unsupported_protocol"
    DUPLICATE_PROXY = "duplicate_proxy"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
```

**ValidationResult 结构**：
```python
@dataclass
class ValidationResult:
    is_valid: bool
    confidence: float = 1.0
    anomalies: List[AnomalyType]
    anomaly_details: Dict[str, Any]
    warnings: List[str]
```

**主要函数**：
- `validate_ip(ip)` - 验证IP
- `validate_port(port)` - 验证端口
- `validate_protocol(protocol)` - 验证协议
- `validate_proxy(proxy_dict)` - 完整验证

### 20. HTTPValidator (`crawler/http_validator.py`)

**职责**：HTTP 实际请求验证

**验证方式**：
- 通过代理发起真实 HTTP 请求
- 测试目标：httpbin.org, ipify.org 等
- 记录响应时间和成功率

**主要函数**：
- `validate_http_proxy(ip, port, protocol, timeout)` - HTTP验证
- `validate_socks_proxy(ip, port, protocol, timeout)` - SOCKS验证

**验证结果**：
```python
{
    "success": True,
    "latency_ms": 245,
    "response_ip": "1.2.3.4",  # 代理出口IP
    "error": None
}
```

### 21. UniversalDetector (`crawler/universal_detector.py`)

**职责**：检测和提取各种模式的数据

**检测能力**：
- `detect_ips(text)` - IP地址检测
- `detect_ports(text)` - 端口号检测
- `detect_protocols(text)` - 协议检测
- `detect_proxy_patterns(text)` - 代理模式检测

**正则模式**：
```python
IP_PATTERN = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
PORT_PATTERN = r'\b([1-9][0-9]{0,4})\b'
PROTOCOL_PATTERN = r'\b(https?|socks[45]a?)\b'
```

## 📊 数据流详解

### 流程 1: 传统爬虫单次爬取 (run_once)

```
开始
  ↓
1️⃣ 加载数据源 (proxy_sources 表)
  ├─ enabled=1 的所有源
  ├─ 按优先级排序
  └─ 创建任务队列
  ↓
2️⃣ 并发抓取阶段 (SOURCE_WORKERS 个线程)
  ├─→ 线程 1: fetch_source(source_1)
  │   ├─ HTTP GET 请求 (带重试)
  │   ├─ 记录 request_log
  │   ├─ parse_by_source(raw) - 调用对应解析器
  │   │   ├─ parse_geonode() / parse_proxy_list_xxx()
  │   │   └─ 返回 [{ip, port, protocol, ...}, ...]
  │   └─ normalize_record() - 统一字段格式
  │       └─ upsert_proxy() - 写入 MySQL
  │           ├─ 存在: 更新 last_seen_at
  │           └─ 不存在: 插入新记录
  ├─→ 线程 2: fetch_source(source_2)
  ├─→ ...
  └─→ 等待所有源完成
  ↓
3️⃣ 收集所有新代理
  ├─ 去重 (按 ip+port+protocol)
  └─ 创建验证任务队列
  ↓
4️⃣ 并发验证阶段 (VALIDATE_WORKERS 个线程)
  ├─→ 线程 1: tcp_check(ip_1, port_1, timeout)
  │   ├─ socket.connect() 测试
  │   ├─ 记录延迟 latency_ms
  │   ├─ score_proxy(latency_ms, source_count)
  │   │   └─ score = f(延迟, 来源数) [0-100]
  │   └─ update_proxy_check() - 更新 MySQL
  │       ├─ last_checked_at = NOW()
  │       ├─ latency_ms = xxx
  │       ├─ is_alive = 1/0
  │       └─ fail_count++ (失败时)
  ├─→ 线程 2-30: 同时验证其他代理
  └─→ 等待所有验证完成
  ↓
5️⃣ 更新 Redis 快速池
  ├─ 筛选 is_alive=1 的代理
  ├─ 按协议分组
  └─ ZADD 到 Sorted Set (score 为排序依据)
      ├─ proxy:http:US (美国 HTTP 代理)
      ├─ proxy:socks5:CN (中国 SOCKS5 代理)
      └─ ...
  ↓
✅ 完成，打印统计信息
  ├─ 总抓取: X 条
  ├─ 新增: Y 条
  ├─ 可用: Z 条
  └─ 耗时: T 秒
```

### 流程 2: 动态爬虫爬取 (crawl-custom)

```
开始
  ├─ URL: https://example.com/proxies
  ├─ max_pages: 10
  ├─ use_ai: true
  └─ no_store: false
  ↓
1️⃣ 创建会话 (crawl_sessions 表)
  ├─ session_id: 12345
  ├─ url: https://...
  ├─ status: 'running'
  └─ started_at: NOW()
  ↓
2️⃣ 循环爬取页面 (当前页 = 1)
  ↓
  ┌────────────────────────────────────────┐
  │ 3️⃣ 抓取当前页                          │
  │  ├─ HTTP GET (带 User-Agent, Timeout)  │
  │  ├─ 记录 fetch_time_ms                 │
  │  └─ 返回 HTML                           │
  └────────────────────────────────────────┘
  ↓
  ┌────────────────────────────────────────┐
  │ 4️⃣ 通用解析 (UniversalParser)          │
  │  ├─ StructureAnalyzer.analyze_all()    │
  │  │   ├─ find_tables() → 提取表格       │
  │  │   ├─ find_json_blocks() → 提取JSON  │
  │  │   └─ find_lists() → 提取列表        │
  │  ├─ extract_from_tables()              │
  │  │   ├─ 智能列名匹配                   │
  │  │   └─ 提取 [{ip, port, ...}, ...]    │
  │  ├─ extract_from_json()                │
  │  └─ extract_from_text()                │
  │      └─ 正则提取 IP:PORT               │
  └────────────────────────────────────────┘
  ↓
  ┌────────────────────────────────────────┐
  │ 5️⃣ 检查解析结果                        │
  │  ├─ 提取成功 → 继续第 6 步             │
  │  └─ 提取失败/低置信度                  │
  │      ↓                                 │
  │   ErrorHandler.should_use_ai()?        │
  │      ├─ No → 记录失败，继续下一页      │
  │      └─ Yes                            │
  │          ├─ can_afford()? 检查成本     │
  │          ├─ LLMCache.get()? 查缓存     │
  │          └─ LLMCaller.call_llm()       │
  │              ├─ 构建 prompt            │
  │              ├─ OpenAI API 调用        │
  │              ├─ 记录 llm_call_logs     │
  │              ├─ LLMCache.set() 缓存结果│
  │              └─ 返回 {proxies, cost}   │
  └────────────────────────────────────────┘
  ↓
  ┌────────────────────────────────────────┐
  │ 6️⃣ 去重和验证                          │
  │  ├─ 去重 (与已抓取的对比)              │
  │  ├─ ProxyValidator.validate_proxy()    │
  │  │   ├─ 格式验证 (IP/端口/协议)       │
  │  │   ├─ 语义验证 (私网IP/保留地址)    │
  │  │   └─ 返回 ValidationResult          │
  │  └─ 筛选 valid=True 的代理             │
  └────────────────────────────────────────┘
  ↓
  ┌────────────────────────────────────────┐
  │ 7️⃣ 存储和审核                          │
  │  ├─ confidence >= 0.8                  │
  │  │   └─ Storage.upsert_proxy()         │
  │  │       └─ 直接存入 proxy_ips         │
  │  └─ confidence < 0.8                   │
  │      └─ 进入 review_queue               │
  │          ├─ ip, port, protocol         │
  │          ├─ confidence, reason         │
  │          └─ status: 'pending'          │
  └────────────────────────────────────────┘
  ↓
  ┌────────────────────────────────────────┐
  │ 8️⃣ 记录页面日志 (page_logs 表)         │
  │  ├─ session_id: 12345                  │
  │  ├─ url: https://...?page=1            │
  │  ├─ extracted_count: 20                │
  │  ├─ valid_count: 18                    │
  │  ├─ ai_used: 1                         │
  │  ├─ ai_reason: 'low_confidence'        │
  │  └─ fetch_time_ms, parse_time_ms       │
  └────────────────────────────────────────┘
  ↓
  ┌────────────────────────────────────────┐
  │ 9️⃣ 分页检测 (PaginationDetector)       │
  │  ├─ detect_pagination()                │
  │  │   ├─ 检测 URL 参数 (?page=1)       │
  │  │   ├─ 检测 <link rel="next">        │
  │  │   ├─ 检测 "下一页" 链接            │
  │  │   └─ 检测数字页码链接              │
  │  └─ 返回 PaginationInfo                │
  │      ├─ has_pagination: true           │
  │      ├─ next_page_url: https://...?p=2 │
  │      └─ confidence: 0.95               │
  └────────────────────────────────────────┘
  ↓
  ┌────────────────────────────────────────┐
  │ 🔟 PaginationController 决策            │
  │  ├─ current_page < max_pages?          │
  │  ├─ pages_no_new_ip < 3?               │
  │  └─ has_next_page?                     │
  │      ├─ 全部 Yes → 继续爬取下一页      │
  │      └─ 任一 No → 停止                 │
  └────────────────────────────────────────┘
  ↓
  当前页++ → 回到第 3 步
  ↓
🔚 爬取完成
  ├─ 更新 crawl_sessions
  │   ├─ status: 'completed'
  │   ├─ completed_at: NOW()
  │   ├─ pages_crawled, extracted, valid, stored
  │   └─ 统计信息
  └─ 返回 DynamicCrawlResult
      ├─ total_extracted: 180
      ├─ total_valid: 165
      ├─ total_stored: 150
      ├─ pages_crawled: 9
      ├─ ai_calls: 2
      └─ total_cost_usd: 0.0015
```

### 流程 3: 获取代理 (get-proxy)

```
CLI 命令: ip-pool get-proxy --protocol http --country US --count 5
  ↓
1️⃣ 加载配置
  ├─ Settings.from_env()
  └─ ProxyPicker(storage)
  ↓
2️⃣ ProxyPicker.pick_proxies(count=5, protocol='http', country='US')
  ↓
  ┌────────────────────────────────────────┐
  │ 3️⃣ 尝试 Redis 快速池                   │
  │  ├─ 构建键: proxy:http:US              │
  │  ├─ ZREVRANGE 0 4 (取前 5 个高分代理)  │
  │  └─ 返回: ['1.2.3.4:8080', ...]        │
  └────────────────────────────────────────┘
  ↓
  Redis 有结果? ──Yes──> 4️⃣ 返回代理列表
  ↓ No
  ┌────────────────────────────────────────┐
  │ 5️⃣ 回退到 MySQL                        │
  │  ├─ SELECT * FROM proxy_ips            │
  │  ├─ WHERE protocol = 'http'            │
  │  ├─ AND country = 'US'                 │
  │  ├─ AND is_alive = 1                   │
  │  ├─ AND is_deleted = 0                 │
  │  ├─ ORDER BY latency_ms ASC            │
  │  └─ LIMIT 5                            │
  └────────────────────────────────────────┘
  ↓
4️⃣ 格式化输出
  ├─ JSON 格式 (默认)
  │   [{
  │     "ip": "1.2.3.4",
  │     "port": 8080,
  │     "protocol": "http",
  │     "country": "US",
  │     "latency_ms": 120
  │   }, ...]
  └─ TEXT 格式 (--format text)
      1.2.3.4:8080
      5.6.7.8:3128
      ...
```

### 流程 4: 批量检查 (check)

```
CLI 命令: ip-pool check
  ↓
1️⃣ 加载配置
  ├─ CHECK_BATCH_SIZE: 1000
  ├─ VALIDATE_WORKERS: 30
  ├─ FAIL_WINDOW_HOURS: 24
  └─ FAIL_THRESHOLD: 5
  ↓
2️⃣ 批量获取待检查代理
  ├─ SELECT * FROM proxy_ips
  ├─ WHERE is_deleted = 0
  ├─ ORDER BY last_checked_at ASC
  └─ LIMIT 1000
  ↓
3️⃣ 并发验证 (30 个线程)
  ├─→ 线程 1: 检查代理 1
  │   ├─ tcp_check(ip, port, timeout=3)
  │   │   ├─ socket.connect() 尝试连接
  │   │   ├─ 成功: 记录 latency_ms
  │   │   └─ 失败: latency_ms = -1
  │   ├─ score_proxy(latency_ms)
  │   └─ update_proxy_check()
  │       ├─ 成功:
  │       │   ├─ is_alive = 1
  │       │   ├─ fail_count = 0 (重置)
  │       │   ├─ fail_window_start = NULL
  │       │   └─ last_checked_at = NOW()
  │       └─ 失败:
  │           ├─ 首次失败?
  │           │   └─ fail_window_start = NOW()
  │           ├─ fail_count++
  │           ├─ fail_count >= FAIL_THRESHOLD (5)?
  │           │   ├─ Yes → is_alive = 0 (软删除)
  │           │   └─ No → 继续监控
  │           └─ fail_window 过期?
  │               └─ 重置 fail_count, 重新验证
  ├─→ 线程 2-30: 并行检查其他代理
  └─→ 等待所有检查完成
  ↓
4️⃣ 统计结果
  ├─ 可用: 800
  ├─ 不可用: 150
  ├─ 新标记删除: 50
  └─ 总耗时: 45s
  ↓
5️⃣ 更新 Redis 池
  └─ 移除 is_alive=0 的代理
```

## ⚙️ 配置参数详解

### 数据库配置

```bash
# MySQL 配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=ip_pool

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=           # 可选，无密码留空
```

**最佳实践**：
- 生产环境使用独立的数据库用户，权限限制为 `SELECT, INSERT, UPDATE, DELETE`
- Redis 使用专用 DB（如 `REDIS_DB=1`），避免与其他服务冲突
- MySQL 连接池：默认 5 个连接，高并发场景可调整

### HTTP 配置

```bash
# HTTP 请求配置
HTTP_TIMEOUT=10           # 单个请求超时（秒）
HTTP_RETRIES=3            # 失败重试次数
USER_AGENT=Mozilla/5.0... # User-Agent 字符串
```

**调优建议**：
- `HTTP_TIMEOUT`：稳定源建议 5-10 秒，慢速源 15-30 秒
- `HTTP_RETRIES`：3 次重试适合大多数场景，不建议超过 5 次
- `USER_AGENT`：建议模拟常见浏览器，避免被反爬

### 并发配置

```bash
# 并发控制
SOURCE_WORKERS=2          # 并发抓取源数量
VALIDATE_WORKERS=30       # 并发验证代理数量
```

**性能指导**：

| 场景 | SOURCE_WORKERS | VALIDATE_WORKERS | 说明 |
|-----|---------------|-----------------|------|
| 低配 VPS (1核2G) | 1-2 | 10-20 | 避免 CPU/内存过载 |
| 中配服务器 (4核8G) | 2-4 | 30-50 | 默认推荐配置 |
| 高配服务器 (8核16G) | 5-10 | 50-100 | 大规模爬取 |
| 本地测试 | 1 | 10 | 避免 IP 被封 |

**限制因素**：
- `SOURCE_WORKERS` 主要受限于网络带宽（每个源 ~1-5 MB/s）
- `VALIDATE_WORKERS` 主要受限于网络连接数（系统 ulimit -n）

### 检查配置

```bash
# 代理检查配置
CHECK_BATCH_SIZE=1000     # 每批检查数量
FAIL_WINDOW_HOURS=24      # 失败窗口时长（小时）
FAIL_THRESHOLD=5          # 失败次数阈值
CHECK_RETRY_DELAY=1       # 重试延迟（秒）
```

**失败窗口机制详解**：

```
代理首次失败 → 记录 fail_window_start = NOW()
  ↓
在接下来的 24 小时内（FAIL_WINDOW_HOURS）：
  ├─ 每次检查失败 → fail_count++
  ├─ fail_count 达到 5 (FAIL_THRESHOLD) → is_alive=0 (软删除)
  └─ 任一次检查成功 → fail_count 清零，窗口结束
  ↓
24 小时后：
  └─ 窗口过期，重置 fail_count 和 fail_window_start
      └─ 重新开始验证（给代理第二次机会）
```

**推荐配置**：
- 稳定环境：`FAIL_WINDOW_HOURS=24`, `FAIL_THRESHOLD=5`
- 严格模式：`FAIL_WINDOW_HOURS=12`, `FAIL_THRESHOLD=3`
- 宽容模式：`FAIL_WINDOW_HOURS=48`, `FAIL_THRESHOLD=10`

### 日志配置

```bash
# 日志设置
LOG_LEVEL=INFO            # DEBUG | INFO | WARNING | ERROR
LOG_DB_WRITE_ENABLED=true # 是否写入数据库
LOG_DB_MASK_SENSITIVE=true # 是否脱敏敏感信息
```

**日志级别指南**：
- `DEBUG`：开发/调试，输出所有细节（含 SQL 语句、HTTP 请求）
- `INFO`：生产推荐，记录关键操作和统计
- `WARNING`：仅记录警告和错误
- `ERROR`：仅记录错误

**脱敏示例**：
```
原始: IP=192.168.1.100, API_KEY=sk-abc123xyz
脱敏: IP=192.168.1.***, API_KEY=sk-***
```

### 🆕 动态爬虫配置

```bash
# LLM 配置
LLM_ENABLED=true                      # 启用 LLM
LLM_API_KEY=sk-xxx                    # OpenAI API Key
LLM_BASE_URL=https://api.openai.com/v1 # API 地址
LLM_MODEL=gpt-4o-mini                 # 模型名称

# 成本控制
LLM_COST_LIMIT_USD=10.0               # 成本上限（美元）
LLM_CACHE_ENABLED=true                # 启用缓存
LLM_CACHE_TTL_HOURS=168               # 缓存有效期（7天）

# 触发条件（至少一个为 true）
LLM_TRIGGER_ON_LOW_CONFIDENCE=true    # 低置信度时
LLM_TRIGGER_ON_NO_TABLE=true          # 无表格时
LLM_TRIGGER_ON_FAILED_PARSE=false     # 解析失败时
LLM_TRIGGER_ON_USER_REQUEST=true      # 用户明确要求时
```

**模型选择指南**：

| 模型 | 速度 | 成本 | 准确率 | 推荐场景 |
|-----|-----|------|--------|---------|
| `gpt-4o-mini` | ⚡⚡⚡ 快 | 💰 极低 | ⭐⭐⭐ 高 | 生产环境（推荐） |
| `gpt-4-turbo` | ⚡⚡ 中 | 💰💰💰 高 | ⭐⭐⭐⭐ 极高 | 复杂页面、高精度需求 |
| `gpt-3.5-turbo` | ⚡⚡⚡ 快 | 💰 低 | ⭐⭐ 中 | 简单页面、预算有限 |

**成本估算**（假设每页 2000 tokens 输入，200 tokens 输出）：

```python
# gpt-4o-mini
cost_per_page = (2000/1000 * $0.00015) + (200/1000 * $0.00060)
              = $0.0003 + $0.00012
              = $0.00042
              
# 爬取 100 页的成本
100 * $0.00042 = $0.042 (~0.3 CNY)

# gpt-4-turbo  
cost_per_page = (2000/1000 * $0.01) + (200/1000 * $0.03)
              = $0.02 + $0.006
              = $0.026
              
# 爬取 100 页的成本
100 * $0.026 = $2.60 (~18.5 CNY)
```

**成本控制建议**：
- 开发/测试：`LLM_COST_LIMIT_USD=1.0`（约 7 CNY）
- 小规模生产：`LLM_COST_LIMIT_USD=10.0`（约 70 CNY）
- 大规模生产：`LLM_COST_LIMIT_USD=100.0`（约 700 CNY）+ 监控告警

**缓存优化**：
- 启用缓存可减少 70-90% 的重复调用成本
- `LLM_CACHE_TTL_HOURS=168`（7天）适合周更新的代理源
- 每日更新的源建议设为 24 小时

### 配置文件示例

完整的 `.env.example` 文件：

```bash
# ======================
# 数据库配置
# ======================
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=ip_pool

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# ======================
# HTTP 配置
# ======================
HTTP_TIMEOUT=10
HTTP_RETRIES=3
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36

# ======================
# 并发配置
# ======================
SOURCE_WORKERS=2
VALIDATE_WORKERS=30

# ======================
# 检查配置
# ======================
CHECK_BATCH_SIZE=1000
FAIL_WINDOW_HOURS=24
FAIL_THRESHOLD=5
CHECK_RETRY_DELAY=1

# ======================
# 日志配置
# ======================
LOG_LEVEL=INFO
LOG_DB_WRITE_ENABLED=true
LOG_DB_MASK_SENSITIVE=true

# ======================
# 🆕 LLM 配置（可选）
# ======================
LLM_ENABLED=false
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

LLM_COST_LIMIT_USD=10.0
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL_HOURS=168

LLM_TRIGGER_ON_LOW_CONFIDENCE=true
LLM_TRIGGER_ON_NO_TABLE=true
LLM_TRIGGER_ON_FAILED_PARSE=false
LLM_TRIGGER_ON_USER_REQUEST=true
```

## 🗄️ 数据库设计

### proxy_sources 表
```sql
CREATE TABLE proxy_sources (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(256) UNIQUE,        -- 源名称
  url TEXT,                         -- 源 URL
  parser_key VARCHAR(64),           -- 解析器类型
  enabled TINYINT(1),               -- 是否启用
  last_fetch_at DATETIME,           -- 上次抓取时间
  fail_count INT,                   -- 连续失败次数
  created_at DATETIME,
  updated_at DATETIME
);
```

### proxy_ips 表
```sql
CREATE TABLE proxy_ips (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  ip VARCHAR(45) NOT NULL,          -- IP 地址
  port INT NOT NULL,                -- 端口
  protocol VARCHAR(16) NOT NULL,    -- 协议
  anonymity VARCHAR(32),            -- 匿名度
  country VARCHAR(64),              -- 国家
  region VARCHAR(64),               -- 地区
  isp VARCHAR(64),                  -- ISP
  source_id BIGINT,                 -- 来源 ID
  first_seen_at DATETIME,           -- 首次发现
  last_seen_at DATETIME,            -- 最后发现
  last_checked_at DATETIME,         -- 最后检查时间
  latency_ms INT,                   -- 延迟（毫秒）
  is_alive TINYINT(1),              -- 是否可用
  is_deleted TINYINT(1),            -- 是否软删除
  fail_window_start DATETIME,       -- 失败窗口开始时间
  fail_count INT,                   -- 失败次数
  
  UNIQUE KEY (ip, port, protocol),
  KEY (is_alive),
  KEY (country),
  KEY (protocol)
);
```

### audit_logs 表（新增）
```sql
CREATE TABLE audit_logs (
  log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  log_level VARCHAR(16),            -- 日志级别
  operation_type VARCHAR(64),       -- 操作类型
  module_name VARCHAR(64),          -- 模块名
  action TEXT,                      -- 操作描述
  sql_operation VARCHAR(16),        -- SQL 操作
  table_name VARCHAR(64),           -- 表名
  affected_rows INT,                -- 影响行数
  duration_ms INT,                  -- 执行时间
  sql_statement TEXT,               -- SQL 语句
  sql_params JSON,                  -- SQL 参数
  request_status_code INT,          -- HTTP 状态码
  request_latency_ms INT,           -- 延迟
  error_code VARCHAR(64),           -- 错误代码
  error_message TEXT,               -- 错误信息
  error_stack TEXT,                 -- 错误堆栈
  created_at DATETIME,              -- 创建时间
  
  KEY (log_level),
  KEY (operation_type),
  KEY (module_name),
  KEY (created_at)
);
```

### 🆕 crawl_sessions 表（动态爬虫会话）
```sql
CREATE TABLE crawl_sessions (
  session_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  url TEXT NOT NULL,                -- 起始URL
  max_pages INT,                    -- 最大页数
  use_ai TINYINT(1),                -- 是否使用AI
  pages_crawled INT DEFAULT 0,      -- 已爬取页数
  extracted INT DEFAULT 0,          -- 提取总数
  valid INT DEFAULT 0,              -- 有效数
  invalid INT DEFAULT 0,            -- 无效数
  stored INT DEFAULT 0,             -- 存储数
  started_at DATETIME,              -- 开始时间
  completed_at DATETIME,            -- 完成时间
  status VARCHAR(32),               -- 状态: running/completed/failed
  error_message TEXT,               -- 错误信息
  
  KEY (started_at),
  KEY (status)
);
```

### 🆕 page_logs 表（页面爬取日志）
```sql
CREATE TABLE page_logs (
  log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id BIGINT,                -- 关联会话
  url TEXT NOT NULL,                -- 页面URL
  page_number INT,                  -- 页码
  extracted_count INT DEFAULT 0,    -- 提取数量
  valid_count INT DEFAULT 0,        -- 有效数量
  ai_used TINYINT(1) DEFAULT 0,     -- 是否使用AI
  ai_reason VARCHAR(64),            -- AI调用原因
  fetch_time_ms INT,                -- 抓取耗时
  parse_time_ms INT,                -- 解析耗时
  created_at DATETIME,              -- 创建时间
  
  KEY (session_id),
  KEY (created_at),
  FOREIGN KEY (session_id) REFERENCES crawl_sessions(session_id)
);
```

### 🆕 review_queue 表（人工审核队列）
```sql
CREATE TABLE review_queue (
  queue_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id BIGINT,                -- 关联会话
  page_log_id BIGINT,               -- 关联页面日志
  ip VARCHAR(45),                   -- IP地址
  port INT,                         -- 端口
  protocol VARCHAR(16),             -- 协议
  confidence FLOAT,                 -- 置信度
  reason VARCHAR(256),              -- 进入队列原因
  raw_data TEXT,                    -- 原始数据
  status VARCHAR(32) DEFAULT 'pending',  -- pending/approved/rejected
  reviewed_at DATETIME,             -- 审核时间
  reviewer VARCHAR(64),             -- 审核人
  created_at DATETIME,              -- 创建时间
  
  KEY (status),
  KEY (created_at),
  KEY (session_id),
  FOREIGN KEY (session_id) REFERENCES crawl_sessions(session_id)
);
```

### 🆕 llm_call_logs 表（LLM调用日志）
```sql
CREATE TABLE llm_call_logs (
  log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id BIGINT,                -- 关联会话
  page_log_id BIGINT,               -- 关联页面日志
  model VARCHAR(64),                -- 模型名称
  input_tokens INT,                 -- 输入tokens
  output_tokens INT,                -- 输出tokens
  cost_usd DECIMAL(10, 6),          -- 成本（美元）
  latency_ms INT,                   -- 延迟
  cached TINYINT(1) DEFAULT 0,      -- 是否缓存
  success TINYINT(1),               -- 是否成功
  error_message TEXT,               -- 错误信息
  created_at DATETIME,              -- 创建时间
  
  KEY (session_id),
  KEY (created_at),
  KEY (model),
  FOREIGN KEY (session_id) REFERENCES crawl_sessions(session_id)
);
```

## 🔑 关键设计决策

### 1. 为什么使用双层存储？

**MySQL（持久化层）**：
- ✅ 持久化存储，数据不丢失
- ✅ 支持复杂查询（JOIN、聚合、排序）
- ✅ 历史记录追溯（`first_seen_at`, `last_seen_at`）
- ✅ 事务支持，数据一致性
- ❌ 查询延迟：~10-50ms

**Redis（缓存层）**：
- ✅ 内存存储，极速访问（<1ms）
- ✅ 高并发支持（10K+ QPS）
- ✅ 自动过期机制
- ✅ Sorted Set 天然支持评分排序
- ❌ 数据易失（重启丢失）

**协同工作**：
```
写入流程：
  爬虫 → MySQL (持久化)
         ↓
  is_alive=1 → Redis (快速池)

读取流程：
  应用 → Redis (优先)
         ↓ 未命中
       MySQL (回退)
```

### 2. 为什么使用软删除？

**硬删除的问题**：
- ❌ 历史数据丢失，无法追溯
- ❌ 代理恢复需重新抓取
- ❌ 统计分析数据不完整

**软删除的优势**：
- ✅ 保留历史记录（`is_deleted=1`）
- ✅ 支持失败窗口机制
- ✅ 允许代理恢复（重新上线的代理）
- ✅ 数据分析更全面

**实现细节**：
```sql
-- 软删除
UPDATE proxy_ips SET is_alive=0, is_deleted=1 WHERE ...

-- 查询只选活跃代理
SELECT * FROM proxy_ips WHERE is_deleted=0 AND is_alive=1

-- 定期清理真正过期的数据（可选）
DELETE FROM proxy_ips 
WHERE is_deleted=1 
  AND last_seen_at < DATE_SUB(NOW(), INTERVAL 90 DAY)
```

### 3. 为什么有自动初始化？

**传统流程痛点**：
```bash
# 手动执行多个 SQL 脚本
mysql -u root -p ip_pool < schema.sql
mysql -u root -p ip_pool < migrations/001_add_audit_logs.sql
mysql -u root -p ip_pool < migrations/002_add_crawl_sessions.sql
# 容易遗漏、顺序错误、重复执行
```

**自动初始化优势**：
```python
# storage.py 自动执行
def __init__(self, settings):
    if not database_exists():
        create_database()
    if not table_exists('proxy_ips'):
        execute_schema('sql/schema.sql')
    # 零配置，开箱即用
```

- ✅ 简化部署流程（无需手动执行 SQL）
- ✅ 自动恢复损坏的表结构
- ✅ 多环境一致性（开发/测试/生产）
- ✅ Docker/容器化友好

### 4. 为什么记录审计日志？

**业务价值**：

1. **性能监控**
   ```sql
   -- 慢操作分析
   SELECT operation_type, AVG(duration_ms), COUNT(*)
   FROM audit_logs
   WHERE created_at > DATE_SUB(NOW(), INTERVAL 1 DAY)
   GROUP BY operation_type
   ORDER BY AVG(duration_ms) DESC;
   ```

2. **故障诊断**
   ```sql
   -- 错误追踪
   SELECT * FROM audit_logs
   WHERE log_level = 'ERROR'
     AND created_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)
   ORDER BY created_at DESC;
   ```

3. **安全审计**
   ```sql
   -- 谁在什么时间做了什么
   SELECT module_name, action, sql_operation, created_at
   FROM audit_logs
   WHERE sql_operation IN ('DELETE', 'UPDATE')
   ORDER BY created_at DESC;
   ```

4. **统计分析**
   ```sql
   -- 数据源成功率
   SELECT 
     action,
     SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) AS success,
     COUNT(*) AS total,
     ROUND(100.0 * SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS success_rate
   FROM audit_logs
   WHERE operation_type = 'fetch_source'
   GROUP BY action;
   ```

### 5. 为什么选择双引擎架构？

**单引擎方案的局限**：
- ❌ 仅传统爬虫：无法快速适配新源，开发成本高
- ❌ 仅AI爬虫：成本高、依赖外部API、不适合稳定源

**双引擎优势**：

| 维度 | 传统引擎 | 动态引擎 | 双引擎协作 |
|-----|---------|---------|-----------|
| **成本** | 极低 | 中-高 | 低（按需使用AI） |
| **速度** | 快 | 中 | 快（优先传统） |
| **覆盖** | 有限 | ♾️ 无限 | 最大化 |
| **维护** | 高 | 低 | 中 |

**实际应用场景**：
```
已知稳定源（如 Geonode）：
  → 使用传统引擎 (Pipeline)
  → 无AI成本，速度快，准确率高

新发现的代理源：
  → 使用动态引擎 (DynamicCrawler)
  → AI 辅助解析，快速验证
  → 如效果好，后续可转为传统引擎（开发专用解析器）

临时/一次性需求：
  → 使用动态引擎
  → 无需写代码，即刻可用
```

### 6. 为什么需要失败窗口机制？

**问题场景**：
```
代理 A 在 10:00 失败（临时网络问题）
  → 立即标记删除？太激进，可能是误判
  
代理 B 连续失败 10 次（真正不可用）
  → 仍保留？浪费资源，影响池质量
```

**失败窗口解决方案**：
```python
# 首次失败：记录时间窗口
fail_window_start = NOW()
fail_count = 1

# 后续检查：
if NOW() - fail_window_start < 24h:
    # 窗口内，累计失败次数
    fail_count += 1
    if fail_count >= 5:
        is_alive = 0  # 标记删除
else:
    # 窗口过期，给第二次机会
    fail_window_start = NULL
    fail_count = 0
```

**优势**：
- ✅ 容错性：临时故障不会立即删除
- ✅ 准确性：持续失败才标记删除
- ✅ 自愈性：窗口过期后自动恢复验证
- ✅ 可配置：窗口时长和阈值可调整

## 🛠️ 故障排查指南

### 常见问题 1: 爬虫无法连接数据库

**现象**：
```
ERROR: (2003, "Can't connect to MySQL server on 'localhost' (10061)")
```

**排查步骤**：
1. 检查 MySQL 服务是否运行
   ```bash
   # Windows
   net start MySQL
   
   # Linux
   sudo systemctl status mysql
   ```

2. 验证配置文件 `.env`
   ```bash
   MYSQL_HOST=localhost  # 确认主机地址
   MYSQL_PORT=3306       # 确认端口
   MYSQL_USER=root       # 确认用户名
   MYSQL_PASSWORD=xxx    # 确认密码
   ```

3. 测试连接
   ```bash
   mysql -h localhost -u root -p
   ```

4. 检查防火墙
   ```bash
   # Linux
   sudo ufw allow 3306
   ```

### 常见问题 2: Redis 连接失败

**现象**：
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**排查步骤**：
1. 检查 Redis 服务
   ```bash
   # Windows
   redis-server
   
   # Linux
   sudo systemctl status redis
   ```

2. 测试连接
   ```bash
   redis-cli ping
   # 应返回: PONG
   ```

3. 检查配置
   ```bash
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   REDIS_PASSWORD=        # 如无密码留空
   ```

### 常见问题 3: 代理源抓取失败

**现象**：
```
WARNING: Source 'geonode' failed: HTTPError 403 Forbidden
```

**原因分析**：
- 🚫 IP 被封禁（反爬虫）
- 🚫 User-Agent 被拒绝
- 🚫 源网站故障
- 🚫 网络连接问题

**解决方案**：
```python
# 1. 更换 User-Agent
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64)...

# 2. 增加重试次数
HTTP_RETRIES=5

# 3. 增加超时时间
HTTP_TIMEOUT=30

# 4. 查看审计日志
SELECT * FROM audit_logs
WHERE operation_type = 'fetch_source'
  AND error_code IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;
```

### 常见问题 4: LLM API 调用失败

**现象**：
```
ERROR: LLM API call failed: 401 Unauthorized
```

**排查步骤**：
1. 验证 API Key
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $LLM_API_KEY"
   ```

2. 检查成本限制
   ```sql
   SELECT SUM(cost_usd) FROM llm_call_logs
   WHERE created_at > DATE_SUB(NOW(), INTERVAL 1 DAY);
   ```

3. 查看错误日志
   ```sql
   SELECT * FROM llm_call_logs
   WHERE success = 0
   ORDER BY created_at DESC
   LIMIT 10;
   ```

4. 测试备用 API
   ```bash
   # 使用兼容的第三方 API
   LLM_BASE_URL=https://api.deepseek.com/v1
   LLM_MODEL=deepseek-chat
   ```

### 常见问题 5: 代理池一直为空

**现象**：
```bash
$ ip-pool get-proxy --count 10
# 返回: []
```

**诊断流程**：
```bash
# 1. 检查数据库是否有数据
mysql -u root -p -e "SELECT COUNT(*) FROM ip_pool.proxy_ips;"

# 2. 检查是否有可用代理
mysql -u root -p -e "
  SELECT COUNT(*) FROM ip_pool.proxy_ips 
  WHERE is_alive=1 AND is_deleted=0;
"

# 3. 检查 Redis
redis-cli KEYS "proxy:*"
redis-cli ZCARD proxy:http:ALL

# 4. 运行诊断命令
ip-pool diagnose-proxy-pool
```

**可能原因**：
- ❌ 从未运行过爬虫 → 执行 `ip-pool run`
- ❌ 所有代理失效 → 执行 `ip-pool check`
- ❌ Redis 未同步 → 重启爬虫或手动同步

### 常见问题 6: 内存占用过高

**现象**：
```bash
$ top
# python 进程占用 2GB+ 内存
```

**排查步骤**：
1. 检查批量大小
   ```bash
   CHECK_BATCH_SIZE=1000  # 减少到 500
   ```

2. 检查并发数
   ```bash
   VALIDATE_WORKERS=30    # 减少到 20
   ```

3. 检查是否有内存泄漏
   ```python
   # 使用 memory_profiler
   pip install memory-profiler
   python -m memory_profiler main.py
   ```

4. 清理过期日志
   ```sql
   DELETE FROM audit_logs 
   WHERE created_at < DATE_SUB(NOW(), INTERVAL 7 DAY);
   ```

### 诊断工具

**1. 系统验证**
```bash
# 一键检查所有依赖和配置
python verify_system.py

# 输出示例：
✅ Python 3.10.0
✅ MySQL 5.7.42 (connected)
✅ Redis 6.0.16 (connected)
✅ All tables exist
❌ Missing columns in proxy_ips: fail_window_start
```

**2. 代理池诊断**
```bash
ip-pool diagnose-proxy-pool

# 输出：
Total proxies: 5432
Active (is_alive=1): 3210
Deleted (is_alive=0): 2222
Redis cached: 3150
...
```

**3. 日志分析**
```bash
ip-pool diagnose-logs --hours 24

# 输出：
Last 24 hours:
- Total operations: 12,450
- Errors: 23 (0.18%)
- Slow queries (>1s): 5
- Top error: 'Connection timeout' (15 times)
```

## 🔧 扩展性设计

### 1. 水平扩展

**多实例部署**：
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Instance 1 │    │  Instance 2 │    │  Instance 3 │
│  (爬虫)     │    │  (验证)     │    │  (API服务)  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       └──────────────────┴──────────────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
          ┌─────▼─────┐       ┌────▼─────┐
          │   MySQL   │       │  Redis   │
          └───────────┘       └──────────┘
```

**实例分工**：
- **实例 1**：专门运行 `ip-pool run`（爬虫）
- **实例 2**：专门运行 `ip-pool check`（验证）
- **实例 3**：提供 API 接口（`get-proxy`）

**配置示例**：
```bash
# Instance 1: 爬虫
SOURCE_WORKERS=10
VALIDATE_WORKERS=0   # 不参与验证

# Instance 2: 验证
SOURCE_WORKERS=0     # 不参与爬取
VALIDATE_WORKERS=100

# Instance 3: API
# 仅读取 Redis/MySQL，无并发限制
```

### 2. 添加新数据源

**传统方式**（固定解析器）：

```python
# 1. sources.py - 添加新源
SOURCES = [
    # ...existing sources
    {
        "name": "my_new_source",
        "url": "https://example.com/proxies",
        "parser_key": "my_new_source",
        "enabled": True
    }
]

# 2. parsers.py - 实现解析器
def parse_my_new_source(raw: str) -> list:
    """解析 my_new_source 的数据格式"""
    # 根据实际格式实现
    soup = BeautifulSoup(raw, 'html.parser')
    proxies = []
    for row in soup.select('table.proxy tr'):
        proxies.append({
            'ip': row.select_one('.ip').text,
            'port': int(row.select_one('.port').text),
            'protocol': 'http'
        })
    return proxies

# 3. parsers.py - 注册解析器
PARSER_MAP = {
    # ...existing parsers
    "my_new_source": parse_my_new_source
}
```

**动态方式**（无需代码）：

```bash
# 直接使用动态爬虫
ip-pool crawl-custom https://example.com/proxies \
  --max-pages 5 \
  --use-ai
  
# 验证效果后，可选择：
# - 继续使用动态爬虫（灵活）
# - 转为固定解析器（性能优化）
```

### 3. 添加新字段

**场景**：需要记录代理的"响应时间"字段

**步骤**：

```sql
-- 1. 修改表结构
ALTER TABLE proxy_ips 
ADD COLUMN response_time_ms INT DEFAULT NULL COMMENT '响应时间（毫秒）';

-- 2. 添加索引（如需要）
CREATE INDEX idx_response_time ON proxy_ips(response_time_ms);
```

```python
# 3. 修改代码
# storage.py - upsert_proxy()
def upsert_proxy(self, proxy_dict):
    sql = """
        INSERT INTO proxy_ips 
          (ip, port, protocol, ..., response_time_ms)
        VALUES 
          (%s, %s, %s, ..., %s)
        ON DUPLICATE KEY UPDATE
          ..., response_time_ms = VALUES(response_time_ms)
    """
    params = (
        proxy_dict['ip'],
        proxy_dict['port'],
        ...,
        proxy_dict.get('response_time_ms')  # 新增字段
    )
```

### 4. 集成外部服务

**场景 1：Slack 告警**

```python
# notifications.py
import requests

def send_slack_alert(message: str):
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if not webhook_url:
        return
    
    requests.post(webhook_url, json={
        'text': f"🚨 IP Pool Alert: {message}"
    })

# 使用示例
if fail_rate > 0.5:
    send_slack_alert(f"High failure rate: {fail_rate:.1%}")
```

**场景 2：Prometheus 监控**

```python
# metrics.py
from prometheus_client import Gauge, Counter, start_http_server

# 定义指标
proxy_count = Gauge('proxy_pool_count', 'Total proxies', ['status'])
validation_duration = Gauge('validation_duration_seconds', 'Validation time')
errors_total = Counter('errors_total', 'Error count', ['type'])

# 更新指标
proxy_count.labels(status='active').set(3210)
validation_duration.set(45.2)
errors_total.labels(type='connection_timeout').inc()

# 启动 metrics server
start_http_server(9090)  # http://localhost:9090/metrics
```

**场景 3：对接自定义 LLM**

```python
# llm_caller.py
def call_custom_llm(prompt: str) -> dict:
    """对接自定义 LLM API"""
    response = requests.post(
        os.getenv('CUSTOM_LLM_URL'),
        headers={'Authorization': f"Bearer {os.getenv('CUSTOM_LLM_KEY')}"},
        json={'prompt': prompt, 'max_tokens': 500}
    )
    return response.json()

# .env
CUSTOM_LLM_URL=https://your-llm-api.com/v1/chat
CUSTOM_LLM_KEY=your-api-key
```

### 5. 插件系统（高级）

**设计目标**：允许用户编写自定义插件，无需修改核心代码

```python
# plugins/base.py
class Plugin:
    def on_proxy_fetched(self, proxy: dict) -> dict:
        """代理抓取后钩子"""
        return proxy
    
    def on_proxy_validated(self, proxy: dict, valid: bool) -> None:
        """代理验证后钩子"""
        pass

# plugins/geo_enrichment.py
class GeoEnrichmentPlugin(Plugin):
    """地理位置增强插件"""
    
    def on_proxy_fetched(self, proxy: dict) -> dict:
        # 调用 IP 地理位置 API
        geo = requests.get(f"http://ip-api.com/json/{proxy['ip']}").json()
        proxy['city'] = geo.get('city')
        proxy['timezone'] = geo.get('timezone')
        return proxy

# main.py - 加载插件
plugins = load_plugins('plugins/')  # 自动发现插件
for plugin in plugins:
    pipeline.register_plugin(plugin)
```

## 🚀 性能优化

### 1. 并发优化

**当前实现**：
- 抓取和验证使用独立线程池 (`ThreadPoolExecutor`)
- 避免阻塞主流程
- 异常隔离：单个任务失败不影响其他任务

**优化策略**：

```python
# 动态调整并发数
import os
cpu_count = os.cpu_count() or 2
SOURCE_WORKERS = min(cpu_count, 5)        # 最多 5 个抓取线程
VALIDATE_WORKERS = min(cpu_count * 10, 100)  # 最多 100 个验证线程
```

**瓶颈分析**：
- **CPU 密集型**：解析 HTML、JSON → 增加 `SOURCE_WORKERS`
- **IO 密集型**：TCP 验证、HTTP 请求 → 增加 `VALIDATE_WORKERS`
- **内存限制**：批量处理太大 → 减少 `CHECK_BATCH_SIZE`

### 2. 数据库优化

**索引设计**：
```sql
-- 高频查询索引
CREATE INDEX idx_is_alive ON proxy_ips(is_alive);
CREATE INDEX idx_protocol ON proxy_ips(protocol);
CREATE INDEX idx_country ON proxy_ips(country);
CREATE INDEX idx_last_checked ON proxy_ips(last_checked_at);

-- 复合索引（提升特定查询）
CREATE INDEX idx_alive_protocol_country 
  ON proxy_ips(is_alive, protocol, country);
```

**查询优化**：
```python
# ❌ 低效：多次单条查询
for proxy in proxies:
    storage.upsert_proxy(proxy)

# ✅ 高效：批量 UPSERT
storage.batch_upsert_proxies(proxies, batch_size=1000)
```

**连接池配置**：
```python
# config.py
MYSQL_POOL_SIZE = 10           # 连接池大小
MYSQL_POOL_RECYCLE = 3600      # 连接回收时间（秒）
MYSQL_POOL_TIMEOUT = 30        # 获取连接超时
```

### 3. Redis 优化

**数据结构选择**：
```python
# 当前实现：Sorted Set（有序集合）
ZADD proxy:http:US 95 "1.2.3.4:8080"
ZREVRANGE proxy:http:US 0 9  # 获取前 10 个高分代理

# 优势：
# - 自动按 score 排序
# - 范围查询高效 O(log(N)+M)
# - 支持过期时间
```

**内存优化**：
```bash
# Redis 配置
maxmemory 2gb
maxmemory-policy allkeys-lru  # LRU 淘汰策略

# 设置过期时间
EXPIRE proxy:http:US 86400    # 24 小时过期
```

**Pipeline 批量操作**：
```python
# ❌ 低效：多次网络往返
for proxy in proxies:
    redis.zadd(key, {proxy: score})

# ✅ 高效：Pipeline 批量
pipe = redis.pipeline()
for proxy in proxies:
    pipe.zadd(key, {proxy: score})
pipe.execute()  # 一次性执行
```

### 4. 内存优化

**流式处理**：
```python
# ❌ 低效：一次性加载所有代理
all_proxies = storage.fetch_all_proxies()  # 可能上万条
for proxy in all_proxies:
    process(proxy)

# ✅ 高效：分批流式处理
batch_size = 1000
offset = 0
while True:
    batch = storage.fetch_proxies_batch(offset, batch_size)
    if not batch:
        break
    for proxy in batch:
        process(proxy)
    offset += batch_size
```

**对象复用**：
```python
# 复用 BeautifulSoup 解析器
from bs4 import BeautifulSoup

# ❌ 每次创建新解析器
def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    # ...

# ✅ 复用解析器（如适用）
parser = 'lxml' if lxml_available else 'html.parser'
def parse_html(html):
    soup = BeautifulSoup(html, parser)
    # ...
```

### 5. 网络优化

**连接复用**：
```python
import requests

# ✅ 使用 Session 复用连接
session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT})

# 支持 HTTP keep-alive
for url in urls:
    response = session.get(url, timeout=10)
```

**代理验证优化**：
```python
# 当前：TCP 连接测试（快速）
tcp_check(ip, port, timeout=3)

# 可选：HTTP 实际请求测试（准确）
http_validate(ip, port, protocol, timeout=5)

# 混合策略：
# 1. 先 TCP 快速筛选（3秒超时）
# 2. 再 HTTP 精确验证（5秒超时）
```

### 6. LLM 调用优化

**缓存策略**：
```python
# 三级缓存
1. 内存缓存 (LRU, 100 条)
   └─ 命中率：~30%，延迟：<1ms

2. Redis 缓存 (24 小时)
   └─ 命中率：~50%，延迟：~10ms

3. LLM API 调用
   └─ 命中率：~20%，延迟：~2000ms
```

**Prompt 优化**：
```python
# ❌ 低效：发送完整 HTML（可能 100KB+）
prompt = f"Extract proxies from:\n{full_html}"

# ✅ 高效：仅发送关键部分（<5KB）
relevant_html = extract_relevant_section(html)
prompt = f"Extract proxies from:\n{relevant_html[:2000]}"
```

**批量处理**：
```python
# 如果 API 支持批量
prompts = [build_prompt(html) for html in html_list]
responses = llm.batch_call(prompts)  # 一次调用
```

### 7. 监控和诊断

**性能指标**：
```python
# 记录关键操作耗时
with Timer("fetch_source"):
    html = fetch_source(url)
    
# audit_logs 表记录
{
  "operation_type": "fetch_source",
  "duration_ms": 1250,
  "request_latency_ms": 1200,
  ...
}
```

**慢查询分析**：
```sql
-- MySQL 慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;  -- 超过 1 秒的查询

-- 分析慢查询
SELECT * FROM mysql.slow_log
ORDER BY query_time DESC
LIMIT 10;
```

**资源监控**：
```bash
# CPU 和内存
top -p $(pgrep -f "python.*main.py")

# 网络连接数
netstat -an | grep ESTABLISHED | wc -l

# MySQL 连接数
SHOW PROCESSLIST;

# Redis 内存使用
redis-cli INFO memory
```

### 性能基准测试

**测试环境**：
- 4核8G 服务器
- MySQL 5.7 + Redis 6.0
- 100Mbps 网络带宽

**传统爬虫性能**：
```
配置：
- SOURCE_WORKERS=4
- VALIDATE_WORKERS=50
- 10 个预设源

结果：
- 抓取耗时: 45s
- 验证耗时: 180s (3000 个代理)
- 总耗时: ~4 分钟
- 成功率: 65%
- 吞吐量: ~16 代理/秒
```

**动态爬虫性能**（无 AI）：
```
配置：
- max_pages=10
- use_ai=false

结果：
- 平均每页: 8s (抓取 3s + 解析 5s)
- 10 页总耗时: ~80s
- 提取代理: ~200 条
- 吞吐量: ~2.5 代理/秒
```

**动态爬虫性能**（启用 AI）：
```
配置：
- max_pages=10
- use_ai=true
- model=gpt-4o-mini

结果：
- 平均每页: 12s (抓取 3s + 解析 5s + AI 4s)
- 缓存命中率: 70%
- 10 页总耗时: ~120s
- AI 调用次数: 3 次（7 页缓存命中）
- 总成本: $0.0015
- 准确率: 95%+
```

---

## 📚 总结

### 核心设计理念

1. **渐进式增强**：从简单开始，按需升级
   - 基础功能无需 AI，成本为零
   - 遇到复杂场景时才启用 AI
   - 系统设计支持从手动到自动的平滑过渡

2. **可观测性优先**：让系统透明可控
   - 全流程审计日志
   - 详细的性能指标
   - 完善的诊断工具
   - 支持自定义监控集成

3. **容错与自愈**：减少人工干预
   - 失败窗口机制自动恢复
   - 软删除允许数据恢复
   - 异常隔离防止雪崩
   - 降级策略保证服务可用

4. **模块化与可扩展**：面向变化设计
   - 双引擎架构各司其职
   - 核心组件可独立替换
   - 插件系统支持定制
   - 水平扩展无缝支持

### 技术栈一览

```
┌─────────────────────────────────────────────────────┐
│  编程语言    Python 3.10+                           │
├─────────────────────────────────────────────────────┤
│  数据库      MySQL 5.7+ (持久化)                    │
│              Redis 3.0+ (缓存)                      │
├─────────────────────────────────────────────────────┤
│  核心库      requests (HTTP 客户端)                 │
│              BeautifulSoup4 (HTML 解析)             │
│              pymysql (MySQL 驱动)                   │
│              redis-py (Redis 客户端)                │
├─────────────────────────────────────────────────────┤
│  可选库      playwright (JS 渲染)                   │
│              lxml (快速解析)                        │
├─────────────────────────────────────────────────────┤
│  AI 集成     OpenAI API (gpt-4o-mini/gpt-4-turbo)   │
│              兼容其他 OpenAI-compatible API          │
├─────────────────────────────────────────────────────┤
│  测试        pytest (单元测试)                       │
│              pytest-cov (覆盖率)                    │
└─────────────────────────────────────────────────────┘
```

### 项目指标

**代码规模**：
- Python 源文件：~25 个
- 总代码行数：~8,000 行
- 测试文件：~35 个
- 测试覆盖率：~75%

**数据库设计**：
- 核心表：5 个（proxy_sources, proxy_ips, audit_logs, crawl_sessions, page_logs）
- 辅助表：2 个（review_queue, llm_call_logs）
- 索引数量：~15 个

**功能模块**：
- 传统爬虫模块：9 个
- 动态爬虫模块：12 个
- 共享核心组件：5 个

### 性能参数

**传统爬虫**：
- 并发抓取源：2-10 个
- 并发验证代理：30-100 个
- 吞吐量：~15-20 代理/秒
- 内存占用：~200-500 MB

**动态爬虫**：
- 支持最大页数：100 页
- 平均单页耗时：8-12 秒
- 吞吐量：~2-5 代理/秒
- AI 成本：$0.0004/页（gpt-4o-mini）

**存储性能**：
- MySQL 写入：~1000 条/秒
- MySQL 查询：~10-50ms
- Redis 写入：~10000 条/秒
- Redis 查询：<1ms

### 后续规划

**短期优化**（1-2 个月）：
- [ ] 添加更多预设数据源（目标：20+）
- [ ] 优化 LLM Prompt，提升准确率
- [ ] 实现分布式爬取（多实例协调）
- [ ] 添加 Web UI（代理池管理界面）

**中期增强**（3-6 个月）：
- [ ] 支持 HTTPS/SOCKS5 代理验证
- [ ] 实现代理池智能推荐
- [ ] 添加 Prometheus/Grafana 监控
- [ ] 实现代理质量自学习算法

**长期愿景**（6-12 个月）：
- [ ] 插件市场（社区贡献数据源）
- [ ] 多语言 SDK（Python/Go/Node.js）
- [ ] SaaS 化部署（云服务版本）
- [ ] AI 模型微调（定制化解析）

---

**相关文档**：
- 👉 [快速开始](./QUICK_START.md) - 5分钟上手
- 👉 [命令行参考](./CLI_REFERENCE.md) - 完整命令文档
- 👉 [功能详解](./FEATURES.md) - 10大核心功能
- 👉 [模块API](./MODULES.md) - 16个模块详细文档
- 👉 [审计日志](./AUDIT_LOGGING.md) - 日志系统说明
- 👉 [部署指南](./DEPLOYMENT.md) - 生产环境部署
- 👉 [故障排查](./TROUBLESHOOTING.md) - 常见问题解决

**贡献者**：
- 欢迎提交 Issue 和 Pull Request
- 项目遵循 MIT 开源协议
- 感谢所有贡献者的支持 🙏

**最后更新**：2026-02-13
