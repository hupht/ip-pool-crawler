# 功能详细说明

本文档详细介绍 IP Pool Crawler 的所有核心功能和特性。

## 📑 目录

1. [动态爬虫系统](#1-动态爬虫系统)
2. [AI 辅助解析](#2-ai-辅助解析)
3. [智能分页检测](#3-智能分页检测)
4. [通用数据提取](#4-通用数据提取)
5. [多层验证系统](#5-多层验证系统)
6. [审计日志系统](#6-审计日志系统)
7. [失败窗口机制](#7-失败窗口机制)
8. [双引擎架构](#8-双引擎架构)
9. [成本控制](#9-成本控制)
10. [数据质量保障](#10-数据质量保障)

---

## 1. 动态爬虫系统

### 🎯 核心价值

传统爬虫需要为每个网站编写专用解析器，而动态爬虫可以**自动适应任意代理网站**，无需预先配置。

### ✨ 主要特性

#### 1.1 通用格式支持

自动识别并解析多种数据格式：

**HTML 表格**
```html
<table>
  <tr><th>IP</th><th>Port</th><th>Protocol</th></tr>
  <tr><td>1.2.3.4</td><td>8080</td><td>HTTP</td></tr>
</table>
```
- ✅ 自动识别列名（支持中英文、模糊匹配）
- ✅ 智能列映射（`ip`, `port`, `protocol` 等）
- ✅ 处理跨列合并、嵌套表格

**JSON 数据**
```json
{
  "proxies": [
    {"ip": "1.2.3.4", "port": 8080, "type": "http"}
  ]
}
```
- ✅ 自动提取 JSON 块
- ✅ 递归搜索代理数据
- ✅ 支持嵌套结构

**列表格式**
```html
<ul>
  <li>1.2.3.4:8080 (HTTP)</li>
  <li>5.6.7.8:3128 (HTTPS)</li>
</ul>
```
- ✅ 识别 `<ul>`, `<ol>`, 自定义列表
- ✅ 正则提取 IP:Port
- ✅ 协议关键词检测

**纯文本**
```
1.2.3.4:8080
5.6.7.8:3128
```
- ✅ 正则模式匹配
- ✅ 多种分隔符支持
- ✅ 去重和验证

#### 1.2 自动分页爬取

**支持的分页模式**：

| 模式 | URL 示例 | 说明 |
|------|----------|------|
| 参数分页 | `?page=1`, `?p=2` | 最常见 |
| 偏移分页 | `?offset=0`, `?start=20` | 数据库风格 |
| 游标分页 | `?cursor=abc123` | API 风格 |
| REL 标签 | `<link rel="next">` | HTML5 标准 |
| 数字链接 | `[1] [2] [3] [下一页]` | 传统网站 |

**智能停止策略**：
1. 达到最大页数限制（防止无限循环）
2. 连续 N 页无新 IP（可配置，默认 3 页）
3. 检测到分页循环（相同 URL）
4. 解析失败率过高

**配置参数**（`.env`）：
```bash
MAX_PAGES=10                    # 最大爬取页数
MAX_PAGES_NO_NEW_IP=3           # 连续无新IP停止阈值
PAGE_FETCH_TIMEOUT_SECONDS=30   # 页面抓取超时
```

#### 1.3 页面接口自动发现与运行时回退

当页面 HTML 本身没有明文代理数据时，动态爬虫会自动进入接口发现链路。

**默认回退链路**：
```
HTML启发式解析
  -> API_DISCOVERY（页面 + script 候选接口探测）
  -> RUNTIME_API_SNIFF（可选，Playwright 抓取 xhr/fetch JSON）
```

**页面接口自动发现**：
- ✅ 从 HTML 和脚本中提取候选 API URL
- ✅ 支持白名单/黑名单过滤候选 URL
- ✅ 支持重试与候选数量上限控制

**运行时接口抓取（可选）**：
- ✅ 捕获浏览器运行时 `xhr` / `fetch` 的 JSON 响应
- ✅ 适配签名接口、动态 token 场景
- ✅ 仅在 `RUNTIME_API_SNIFF_ENABLED=true` 且非 `--render-js` 路径触发

**关键配置**（`.env`）：
```bash
API_DISCOVERY_ENABLED=true
API_DISCOVERY_MAX_SCRIPTS=6
API_DISCOVERY_MAX_CANDIDATES=12
API_DISCOVERY_RETRIES=1
API_DISCOVERY_WHITELIST=proxy,ip,/api/,api/,freeagency
API_DISCOVERY_BLACKLIST=
RUNTIME_API_SNIFF_ENABLED=false
RUNTIME_API_SNIFF_MAX_PAYLOADS=20
RUNTIME_API_SNIFF_MAX_RESPONSE_BYTES=200000
```

#### 1.4 会话管理

每次 `crawl-custom` 调用创建一个会话：

**记录内容**：
- 起始 URL
- 配置参数（最大页数、是否使用 AI）
- 统计信息（爬取页数、提取数、有效数、存储数）
- 时间戳（开始、完成）
- 状态（running, completed, failed）

**数据库表**：
```sql
crawl_sessions
  ├── session_id (主键)
  ├── url
  ├── max_pages
  ├── pages_crawled
  ├── extracted / valid / stored
  └── started_at / completed_at
```

**用途**：
- 追踪爬取历史
- 分析数据源质量
- 性能监控
- 故障排查

---

## 2. AI 辅助解析

### 🤖 核心价值

当通用解析器遇到复杂页面结构时，自动调用 LLM 进行智能识别和提取。

### ✨ 主要特性

#### 2.1 触发机制

**自动触发条件**（可配置）：

| 触发条件 | 环境变量 | 说明 |
|----------|----------|------|
| 低置信度 | `LLM_TRIGGER_ON_LOW_CONFIDENCE=true` | 提取结果置信度 < 0.5 |
| 无表格 | `LLM_TRIGGER_ON_NO_TABLE=true` | 页面无识别的结构 |
| 解析失败 | `LLM_TRIGGER_ON_FAILED_PARSE=true` | 通用解析器返回空 |
| 用户请求 | `LLM_TRIGGER_ON_USER_REQUEST=true` | 使用 `--use-ai` 参数 |

**手动触发**：
```bash
python cli.py crawl-custom <url> --use-ai
```

#### 2.2 支持的模型

| 模型 | 成本 (1K tokens) | 推荐场景 |
|------|------------------|----------|
| **gpt-4o-mini** | Input: $0.00015<br>Output: $0.00060 | 日常使用（推荐）|
| gpt-4-turbo | Input: $0.01<br>Output: $0.03 | 复杂页面 |
| gpt-3.5-turbo | Input: $0.0005<br>Output: $0.0015 | 预算有限 |

**配置示例**（`.env`）：
```bash
LLM_ENABLED=true
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

#### 2.3 智能缓存

**缓存策略**：
- **缓存键**：基于 HTML 内容（前 2000 字符）+ 上下文的 SHA256 哈希
- **TTL**：可配置（默认 24 小时）
- **算法**：LRU（最近最少使用）
- **命中率**：通常 60-80%

**成本节省示例**：
```
无缓存：10 次调用 × $0.0005 = $0.005
有缓存：2 次实际调用 × $0.0005 = $0.001
节省：80%
```

**配置**：
```bash
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL_HOURS=24
```

#### 2.4 Prompt 工程

**系统提示词**：
```
你是资深代理数据抽取器。仅输出合法 JSON，不要输出解释、Markdown 或额外文本。
```

**用户提示词模板**：
```
任务：从 HTML 中提取代理列表，并严格返回 JSON。
规则：
1) 仅提取公网 IPv4，过滤私网/保留地址。
2) port 必须是 1-65535 的整数。
3) protocol 统一为 http/https/socks4/socks5，未知时用 http。
4) confidence 取值 0-1。
5) 按 ip+port+protocol 去重。
6) 若未提取到结果，返回 {"proxies":[]}。
输出要求：仅输出 JSON 对象，格式为 {"proxies":[{"ip":"...","port":8080,"protocol":"http","confidence":0.95}]}。
上下文：{context_json}
HTML：
{html_snippet}
```

**可配置项（`.env`）**：
```bash
LLM_SYSTEM_PROMPT=...            # 自定义系统提示词
LLM_USER_PROMPT_TEMPLATE=...     # 自定义用户提示词模板
LLM_SUBMIT_FULL_HTML=false       # true=提交完整页面
LLM_HTML_SNIPPET_CHARS=5000      # false 时提交前 N 字符
```

⚠️ 提示：提交字符越少，提取效果通常越差（上下文不足）。

**返回格式**：
```json
{
  "proxies": [
    {
      "ip": "192.168.1.1",
      "port": 8080,
      "protocol": "http",
      "confidence": 0.9
    }
  ]
}
```

#### 2.5 成本监控

**实时跟踪**：
- 每次调用成本
- 累计成本
- Token 使用量

**成本限制**：
```bash
LLM_COST_LIMIT_USD=1.0  # 单次会话最大成本
```

**日志记录**（`llm_call_logs` 表）：
```sql
CREATE TABLE llm_call_logs (
  log_id BIGINT PRIMARY KEY,
  model VARCHAR(64),
  input_tokens INT,
  output_tokens INT,
  cost_usd DECIMAL(10, 6),
  latency_ms INT,
  cached TINYINT(1),
  created_at DATETIME
);
```

---

## 3. 智能分页检测

### 🔍 核心价值

自动识别网页分页模式，无需手动配置翻页规则。

### ✨ 主要特性

#### 3.1 检测优先级

**优先级从高到低**：

1. **URL 参数推断** (置信度: 0.9)
   ```
   当前URL: https://example.com/proxy?page=2
   检测到参数: page=2
   推测下一页: ?page=3
   ```

2. **REL 标签检测** (置信度: 0.95)
   ```html
   <link rel="next" href="/proxy?page=3">
   <a rel="next" href="/proxy?page=3">下一页</a>
   ```

3. **下一页链接** (置信度: 0.7-0.85)
   ```html
   <a href="/proxy?page=3">下一页</a>
   <a href="/proxy?page=3">Next</a>
   <a href="/proxy?page=3">更多</a>
   ```

4. **数字链接** (置信度: 0.6-0.8)
   ```html
   <a href="?page=1">1</a>
   <a href="?page=2" class="active">2</a>
   <a href="?page=3">3</a>
   ```

#### 3.2 支持的参数名

**页码参数**：
- `page`, `p`, `pagenum`, `page_no`, `pageindex`, `page_idx`

**偏移量参数**：
- `offset`, `start`, `begin`, `pos`, `index`, `item`

**游标参数**：
- `cursor`, `token`, `marker`, `id`, `after`, `before`

#### 3.3 分页信息结构

```python
@dataclass
class PaginationInfo:
    has_pagination: bool              # 是否存在分页
    pagination_type: PaginationType   # 分页类型
    next_page_url: str                # 下一页 URL（完整）
    current_page: int                 # 当前页码
    total_pages: int                  # 总页数（如可提取）
    confidence: float                 # 检测置信度
    detection_method: str             # 检测方法
```

#### 3.4 循环检测

**防止无限循环**：
- 记录已访问 URL
- 检测重复 URL
- 检测参数异常（如页码不递增）

**示例**：
```
第1页: /proxy?page=1
第2页: /proxy?page=2
第3页: /proxy?page=3
第4页: /proxy?page=3  ❌ 检测到循环，停止
```

---

## 4. 通用数据提取

### 📊 核心价值

支持多种数据格式，自动识别并提取代理信息。

### ✨ 主要特性

#### 4.1 表格解析

**智能列匹配**：
```python
COLUMN_ALIASES = {
    'ip': ['ip', 'ip地址', 'ip address', 'host', '主机', '地址'],
    'port': ['port', '端口', '端口号', 'port号'],
    'protocol': ['protocol', '协议', 'type', '类型', 'proto'],
    'country': ['country', '国家', '地区', 'location'],
}
```

**处理能力**：
- ✅ 跨列合并
- ✅ 行列转置
- ✅ 嵌套表格
- ✅ 表头多行
- ✅ 空单元格

**提取流程**：
```
HTML表格 → 识别表头 → 猜测列索引 → 遍历行提取
  ↓
ProxyExtraction {
  ip: "1.2.3.4",
  port: 8080,
  protocol: "http",
  source_type: "table",
  confidence: 0.9
}
```

#### 4.2 JSON 解析

**检测模式**：
1. `<script>` 标签内的 JSON
2. 独立 JSON 块
3. JSONP 格式

**递归搜索**：
```json
{
  "data": {
    "proxies": [
      {"ip": "1.2.3.4", "port": 8080}
    ]
  }
}
```

**字段映射**：
- `ip` / `host` / `address` → IP
- `port` / `port_number` → Port
- `protocol` / `type` / `scheme` → Protocol

#### 4.3 列表解析

**支持的列表类型**：
- `<ul>` / `<ol>` - 标准列表
- `<div class="proxy-item">` - 自定义列表
- `<p>` 连续段落

**提取模式**：
```
文本: "1.2.3.4:8080 (HTTP)"
  ↓
正则: IP_PATTERN + PORT_PATTERN
  ↓
提取: {ip: "1.2.3.4", port: 8080, protocol: "http"}
```

#### 4.4 置信度评估

**置信度来源**：

| 来源 | 置信度 | 原因 |
|------|--------|------|
| HTML 表格 | 0.9 | 结构化数据，列明确 |
| JSON 数据 | 0.95 | 机器可读，最可靠 |
| 列表 | 0.8 | 结构较清晰 |
| 纯文本 | 0.6 | 需正则匹配 |
| AI 提取 | 0.5-0.9 | 由 AI 返回 |

**去重策略**：
- 基于 `(ip, port, protocol)` 三元组
- 保留第一次出现的记录
- 合并额外信息

---

## 5. 多层验证系统

### 🛡️ 核心价值

确保只有真正可用的代理进入池中，提高代理质量。

### ✨ 验证层次

#### 5.1 格式验证

**IP 地址验证**：
```python
# 使用 ipaddress 模块
ip_obj = IPv4Address("192.168.1.1")

# 检查项：
✓ 是否有效 IPv4 格式
✗ 私有 IP (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
✗ 保留地址 (0.0.0.0/8, 127.0.0.0/8, 169.254.0.0/16)
✗ 广播地址 (255.255.255.255)
✗ 组播地址 (224.0.0.0/4)
```

**端口验证**：
```python
# 有效范围
1 <= port <= 65535

# 可疑端口警告
22, 23, 25, 53, 135, 139, 445  # 系统服务
3389, 5900                      # 远程桌面
```

**协议验证**：
```python
SUPPORTED_PROTOCOLS = {
    'http', 'https', 'socks4', 'socks5', 'socks4a'
}
```

#### 5.2 语义验证

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

#### 5.3 TCP 连接测试

**测试方式**：
```python
socket.create_connection((ip, port), timeout=3)
```

**记录指标**：
- 是否成功建立连接
- 连接延迟（毫秒）
- 错误类型（超时、拒绝连接等）

**评分算法**：
```python
def score_proxy(latency_ms: int, source_count: int) -> int:
    """
    延迟越低、来源越多 → 分数越高
    范围: 0-100
    """
    latency_score = max(0, 100 - latency_ms / 10)
    source_bonus = min(20, source_count * 5)
    return min(100, int(latency_score + source_bonus))
```

#### 5.4 HTTP 实际请求（可选）

**验证目标**：
- `http://httpbin.org/ip` - 测试 HTTP
- `https://api.ipify.org` - 测试 HTTPS
- `http://www.google.com` - 测试真实场景

**验证内容**：
- 是否能正常发起请求
- 响应时间
- 返回的出口 IP（验证代理生效）

**配置**：
```bash
HTTP_VALIDATION_ENABLED=false  # 默认关闭（较慢）
HTTP_VALIDATION_TIMEOUT=10     # 超时时间
```

---

## 6. 审计日志系统

### 📊 核心价值

完整记录所有操作，支持故障排查、性能分析、成本追踪。

### ✨ 主要特性

详见 [AUDIT_LOGGING.md](./AUDIT_LOGGING.md)

**记录的操作**：
- 数据库操作（INSERT/UPDATE/DELETE with affected rows）
- HTTP 请求（URL、状态码、字节数、延迟）
- TCP 检查（IP、端口、结果、延迟）
- 流程事件（爬虫启动/完成/错误）
- LLM 调用（模型、tokens、成本、缓存命中）

**脱敏机制**：
```
IP: 192.168.1.100 → 192.168.1.***
密码: mypassword → ***
API Key: sk-abc123 → sk-***
```

---

## 7. 失败窗口机制

### ⏱️ 核心价值

给代理多次验证机会，避免因临时网络问题而误删除。

### ✨ 工作原理

**状态转移**：
```
健康 (is_alive=1, fail_count=0)
  ↓ 首次验证失败
失败中 (is_alive=1, fail_count=1, fail_window_start记录时间)
  ↓ 继续失败
失败中 (fail_count++, 直到达到阈值)
  ↓ fail_count >= FAIL_THRESHOLD
标记删除 (is_alive=0)
  ↓ 窗口过期 (当前时间 - fail_window_start > FAIL_WINDOW_HOURS)
重新验证 (fail_count清零, is_alive恢复1)
```

**配置参数**（`.env`）：
```bash
FAIL_WINDOW_HOURS=24    # 失败窗口时长
FAIL_THRESHOLD=5        # 失败次数阈值
```

**优势**：
- ✅ 容忍临时故障
- ✅ 自动恢复机制
- ✅ 减少误删除
- ✅ 保留历史记录

---

## 8. 双引擎架构

### 🔀 核心价值

同时支持**传统预设源爬虫**和**动态通用爬虫**，满足不同场景需求。

### ✨ 引擎对比

| 特性 | 传统引擎 (Pipeline) | 动态引擎 (DynamicCrawler) |
|------|---------------------|---------------------------|
| **使用场景** | 预设的稳定数据源 | 临时/未知格式网站 |
| **配置需求** | 需预先配置解析器 | 无需配置 |
| **格式支持** | 少数固定格式 | 多种通用格式 |
| **分页支持** | 手动配置 | 自动检测 |
| **AI 辅助** | ❌ | ✅ |
| **性能** | 快（专用解析器） | 较慢（通用解析） |
| **维护成本** | 高（需更新解析器） | 低（自适应） |
| **命令** | `python cli.py run` | `python cli.py crawl-custom` |

### ✨ 共享组件

两个引擎共享以下组件：
- ✅ 存储层（MySQL + Redis）
- ✅ 验证器（TCP + HTTP）
- ✅ 审计日志
- ✅ 配置管理
- ✅ 失败窗口机制

---

## 9. 成本控制

### 💰 核心价值

使用 AI 功能时，严格控制成本，避免意外费用。

### ✨ 控制机制

#### 9.1 成本限制

**单次会话限制**：
```bash
LLM_COST_LIMIT_USD=1.0  # 超过后停止AI调用
```

**实时监控**：
```python
ErrorHandler.accumulated_cost_usd  # 累计成本
```

**超限行为**：
```python
if accumulated_cost >= cost_limit:
    return {
        "proxies": [],
        "skipped": True,
        "reason": "cost_limit_reached"
    }
```

#### 9.2 成本估算

**调用前估算**：
```python
# 当 LLM_SUBMIT_FULL_HTML=false 时，按配置截取
snippet_chars = 5000  # 对应 LLM_HTML_SNIPPET_CHARS
html_snippet = html[:snippet_chars]

# 估算tokens
estimated_tokens = len(html_snippet) / 4  # 约1250 tokens

# 估算成本
estimated_cost = (1250 / 1000) * 0.00015  # ≈ $0.0002
```

#### 9.3 缓存策略

**缓存收益**：
```
场景：爬取同一网站的10页
无缓存：10次 × $0.0005 = $0.005
有缓存：2次 × $0.0005 = $0.001 (80%缓存命中率)
节省：$0.004 (80%)
```

#### 9.4 成本报告

**输出示例**：
```
📊 成本统计:
  AI调用次数: 15
  缓存命中: 12 (80%)
  实际调用: 3
  输入tokens: 3750
  输出tokens: 450
  总成本: $0.00076
```

---

## 10. 数据质量保障

### ✅ 核心价值

确保进入代理池的数据质量高、可用性强。

### ✨ 质量控制点

#### 10.1 入口控制

**解析阶段**：
- 格式验证（IP、端口）
- 语义验证（私网、保留地址）
- 置信度评估

**低置信度处理**：
```python
if confidence < 0.5:
    # 进入审核队列
    insert_review_queue_item(
        proxy_data,
        reason="low_confidence"
    )
```

#### 10.2 验证阶段

**多层验证**：
1. TCP 连接测试（必须）
2. HTTP 请求测试（可选）
3. 延迟测试
4. 评分计算

**失败处理**：
- 记录失败次数和时间
- 启动失败窗口机制
- 达到阈值则软删除

#### 10.3 数据清洗

**去重策略**：
```sql
UNIQUE KEY (ip, port, protocol)
```

**软删除**：
```sql
is_deleted = 1  -- 标记为删除，但保留记录
```

**定期清理**：
```sql
-- 删除长期不可用的代理
DELETE FROM proxy_ips
WHERE is_alive = 0
  AND is_deleted = 1
  AND last_checked_at < NOW() - INTERVAL 30 DAY;
```

#### 10.4 质量监控

**统计指标**：
- 提取成功率（提取数 / 页面数）
- 验证通过率（成功数 / 提取数）
- 平均置信度
- 平均延迟

**质量报告**：
```
会话 #12345
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  爬取页数: 5
  提取总数: 250
  有效代理: 180 (72%)
  平均置信度: 0.82
  平均延迟: 245ms
  AI调用: 2次
  成本: $0.001
```

---

## 🎓 最佳实践

### 使用动态爬虫

1. **首次测试**：使用 `--no-store --verbose` 测试
2. **评估质量**：查看提取数、有效率
3. **决定是否使用 AI**：低质量时启用 `--use-ai`
4. **正式爬取**：去掉 `--no-store`，开始收集

### 成本优化

1. **优先使用缓存**：`LLM_CACHE_ENABLED=true`
2. **选择合适模型**：日常用 `gpt-4o-mini`
3. **设置成本限制**：`LLM_COST_LIMIT_USD=1.0`
4. **监控成本**：查看 `llm_call_logs` 表

### 数据质量

1. **启用所有验证**：格式 + TCP + HTTP（可选）
2. **设置合理的失败窗口**：`FAIL_WINDOW_HOURS=24`
3. **定期检查审核队列**：`SELECT * FROM review_queue WHERE status='pending'`
4. **监控质量指标**：提取率、验证率、平均延迟

---

**相关文档**：
- 👉 [快速开始](./QUICK_START.md)
- 👉 [架构设计](./ARCHITECTURE.md)
- 👉 [模块详解](./MODULES.md)
- 👉 [动态爬虫使用指南](./UNIVERSAL_CRAWLER_USAGE.md)
- 👉 [LLM 集成指南](./LLM_INTEGRATION.md)
