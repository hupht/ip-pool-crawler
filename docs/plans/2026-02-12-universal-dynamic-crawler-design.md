# 通用动态爬虫系统设计文档

**版本:** v1.0  
**日期:** 2026-02-12  
**状态:** 设计阶段

---

## 📌 需求概述

### 目标
用户可以提供**任意网址**，系统自动检测页面中的 IP 地址和端口，无需预先配置解析规则。系统需要处理多页情况，有完善的容错机制，并支持可选的 AI 辅助改进精准度。

### 核心特性
1. **通用检测**：自动识别页面中的 IP+端口特征
2. **结构识别**：自动发现表格、列表、JSON 等数据结构
3. **智能提取**：基于上下文推理缺失的字段（如端口、协议）
4. **多页处理**：自动检测分页，按配置爬取多页
5. **容错系统**：三层容错 + AI 辅助
6. **灵活配置**：支持 LLM 自主配置（base_url、model、apikey）

---

## 🏗️ 系统架构

### 高层流程

```
用户提供 URL + 配置
    ↓
[DynamicCrawler] 主控制器
    ├─ fetcher.py：下载页面
    ├─ [第一层] universal_detector：检测 IP 特征
    ├─ structure_analyzer：识别表格/列表
    ├─ universal_parser：提取数据 + 置信度
    │
    ├─ pagination_controller：检测下一页
    │  ├─ pagination_detector：URL参数 / 链接 / 加载更多
    │
    ├─ [第二层] validator：异常检测
    │  ├─ 格式验证（IP、端口范围）
    │  ├─ 覆盖率检查
    │  └─ 结构异常标记
    │
    ├─ [第三层] ai_fallback：LLM 辅助
    │  ├─ llm_config：LLM 参数管理
    │  ├─ llm_caller：调用 LLM
    │  └─ llm_cache：缓存结果
    │
    └─ storage.py：存储数据 + 去重
```

### 模块清单

| 模块 | 文件 | 职责 |
|------|------|------|
| **检测器** | `universal_detector.py` | 正则匹配 IP+端口、协议等特征 |
| **结构识别** | `structure_analyzer.py` | 识别表格、列表、JSON、纯文本 |
| **通用解析** | `universal_parser.py` | 提取数据 + 计算置信度 |
| **分页控制** | `pagination_controller.py` | 管理多页爬取逻辑 |
| **分页检测** | `pagination_detector.py` | 检测下一页 URL |
| **验证器** | `validator.py` | 异常检测、格式验证 |
| **LLM 配置** | `llm_config.py` | 管理 LLM 参数 + 可选 AI |
| **LLM 调用** | `llm_caller.py` | 与 LLM API 通信 |
| **LLM 缓存** | `llm_cache.py` | 缓存 LLM 结果降低成本 |
| **动态爬虫** | `dynamic_crawler.py` | 主控制器，协调所有模块 |
| **CLI 命令** | `cli.py`（修改） | 新增 `crawl-custom` 和交互式模式 |

---

## 🔧 配置参数 (`.env`)

```bash
# ===== 动态爬虫配置 =====
DYNAMIC_CRAWLER_ENABLED=true

# ----- 启发式检测 -----
HEURISTIC_CONFIDENCE_THRESHOLD=0.5
MIN_EXTRACTION_COUNT=3
ENABLE_STRUCT_AWARE_PARSING=true

# ----- 分页配置 -----
MAX_PAGES=5
MAX_PAGES_NO_NEW_IP=3
CROSS_PAGE_DEDUP=true

# ----- LLM 配置（用户自主填写）-----
USE_AI_FALLBACK=false                           # 默认关闭，用户选择启用
LLM_BASE_URL=https://api.openai.com/v1          # 支持自定义 base_url
LLM_MODEL=gpt-4o-mini                           # 支持自定义 model
LLM_API_KEY=sk-xxx                              # 用户提供 API key
LLM_TIMEOUT_SECONDS=30

# AI 触发条件
AI_TRIGGER_ON_LOW_CONFIDENCE=true
AI_TRIGGER_ON_NO_TABLE=true
AI_TRIGGER_ON_FAILED_PARSE=true
AI_TRIGGER_ON_USER_REQUEST=true

# AI 成本控制
AI_COST_LIMIT_USD=100
AI_CACHE_ENABLED=true
AI_CACHE_TTL_HOURS=24

# ----- 错误处理 -----
ERROR_RECOVERY_MODE=retry        # retry 或 skip
MAX_RETRIES_PER_PAGE=3
RETRY_BACKOFF_SECONDS=5
SAVE_FAILED_PAGES_SNAPSHOT=true

# ----- 审查队列 -----
REQUIRE_MANUAL_REVIEW=false
SAVE_LOW_CONFIDENCE_DATA=true
LOW_CONFIDENCE_THRESHOLD=0.5

# ----- 日志 -----
DYNAMIC_CRAWLER_LOG_LEVEL=INFO
```

---

## 💾 数据库表扩展

### 1. 待审查队列

```sql
CREATE TABLE IF NOT EXISTS proxy_review_queue (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_url VARCHAR(500) NOT NULL,
    ip VARCHAR(15) NOT NULL,
    port INT,
    protocol VARCHAR(10),
    confidence FLOAT COMMENT '提取置信度 0-1',
    extraction_method ENUM('heuristic', 'ai', 'hybrid') COMMENT '提取方法',
    page_number INT COMMENT '页码',
    error_reason TEXT COMMENT '错误原因',
    raw_data JSON COMMENT '原始提取数据',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP NULL,
    reviewed_by VARCHAR(50),
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    INDEX idx_status (status),
    INDEX idx_source_url (source_url)
);
```

### 2. 爬取日志（按页）

```sql
CREATE TABLE IF NOT EXISTS crawl_page_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    crawl_session_id VARCHAR(50) NOT NULL COMMENT '爬取会话 ID',
    source_url VARCHAR(500) NOT NULL,
    page_number INT,
    http_status INT,
    ip_count INT COMMENT '该页提取的 IP 数',
    confidence_avg FLOAT COMMENT '平均置信度',
    error_message TEXT,
    recovery_action ENUM('retry', 'skip', 'ai_fallback', 'none') COMMENT '恢复操作',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INT COMMENT '爬取耗时',
    INDEX idx_session (crawl_session_id),
    INDEX idx_source_url (source_url)
);
```

### 3. LLM 调用记录

```sql
CREATE TABLE IF NOT EXISTS llm_call_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    crawl_session_id VARCHAR(50) NOT NULL,
    source_url VARCHAR(500),
    page_number INT,
    trigger_reason ENUM('low_confidence', 'no_table', 'failed_parse', 'user_request'),
    prompt_tokens INT,
    completion_tokens INT,
    total_cost_usd DECIMAL(10, 6),
    model_used VARCHAR(50),
    response JSON COMMENT '返回的 JSON 结构化结果',
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (crawl_session_id)
);
```

### 4. 爬取会话（关键）

```sql
CREATE TABLE IF NOT EXISTS crawl_session (
    id VARCHAR(50) PRIMARY KEY,
    source_url VARCHAR(500) NOT NULL,
    start_url VARCHAR(500) NOT NULL COMMENT '起始 URL',
    user_config JSON COMMENT '用户配置快照',
    status ENUM('running', 'paused', 'completed', 'failed') DEFAULT 'running',
    total_pages INT,
    total_ips INT,
    total_llm_cost_usd DECIMAL(10, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    error_message TEXT,
    INDEX idx_status (status)
);
```

---

## 📊 核心算法

### 1. IP 特征检测

**正则表达式**：
```python
# IP 地址模式
IP_PATTERN = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'

# IP:PORT 模式
IP_PORT_PATTERN = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):(\d{1,5})\b'

# 端口模式（从 IP 单独出现时推理）
PORT_PATTERN = r'(?:port|端口)[\s:]*(\d{1,5})'
```

### 2. 置信度计算

```python
def calculate_confidence(
    extraction_source: str,      # 'html_table', 'regex', 'json'
    field_presence: dict,        # { 'ip': True, 'port': True, 'protocol': True }
    context_certainty: float,    # 0-1, 上下文推理的可信度
    format_validity: bool        # 格式是否有效
) -> float:
    base_score = {
        'html_table': 0.9,      # 表格提取最可靠
        'json': 0.85,           # JSON 结构可靠
        'regex': 0.6,           # 正则提取较不可靠
    }[extraction_source]
    
    field_bonus = 0.1 if field_presence['ip'] else 0
    field_bonus += 0.05 if field_presence['port'] else 0
    field_bonus += 0.05 if field_presence['protocol'] else 0
    
    total = min(base_score + field_bonus, 1.0)
    total *= context_certainty
    total = total if format_validity else total * 0.5
    
    return round(total, 2)
```

### 3. 分页检测优先级

```
URL 参数推断 (最优先)
  ├─ 检测 page=, offset=, start=, p= 模式
  ├─ 自动递增构造下一页 URL
  └─ 如：page=1 → page=2 → page=3

  ↓（若失败）

链接检测 (中优先)
  ├─ 寻找"下一页"链接
  ├─ 支持中文：下一页、下页、→
  ├─ 支持英文：next, next page, →
  └─ 支持按钮：当前页 + 1

  ↓（若失败）

加载更多 (最低优先)
  ├─ 检测 load-more, show-more 按钮
  └─ 标记为"需要 JS 交互"（可选支持）
```

### 4. 容错流程

```
启发式提取 + 置信度计算
    ↓
IF confidence < threshold OR 格式错误:
    ├─ 标记为"可疑"
    ├─ 写入 proxy_review_queue
    └─ IF use_ai_fallback AND ai_enabled:
        ├─ 调用 LLM
        ├─ 比较 LLM 结果
        └─ 取置信度最高版本

IF 无法提取任何 IP（覆盖率 = 0）:
    ├─ IF error_recovery_mode = 'retry':
    │   └─ 写入断点，标记为 failed，下次重试
    └─ IF error_recovery_mode = 'skip':
        └─ 记录日志，继续下一页

跨页去重（全局）:
    └─ 检查 (IP, port) 组合是否已存在
```

---

## 🎯 分阶段实现计划

见 `2026-02-12-universal-dynamic-crawler-implementation-plan.md`

---

## 📝 相关文档

- **API 文档**：`docs/UNIVERSAL_CRAWLER_API.md`（使用指南）
- **CLI 参考**：`docs/CLI_REFERENCE.md`（新增命令）
- **故障排查**：`docs/TROUBLESHOOTING.md`（常见问题）
- **LLM 集成**：`docs/LLM_INTEGRATION.md`（AI 配置指南）

---

## ✅ 成功标准

1. ✅ 支持用户自主提供 URL，无需预配置
2. ✅ 自动检测 IP+端口，场景覆盖率 > 80%
3. ✅ 支持多页爬取，自动识别分页方式
4. ✅ 容错系统运行，异常数据隔离到待审查队列
5. ✅ LLM 可选集成，支持用户自定义 base_url/model/apikey
6. ✅ 全部集成到 CLI，支持命令行和交互式调用
7. ✅ 文档完整，包括配置、使用、故障排查
