# 通用动态爬虫 - 配置指南

**版本**：1.0  
**日期**：2026-02-12

---

## 📋 概述

通用动态爬虫允许用户提供任意网址，系统自动检测并解析代理 IP。本文档说明所有相关配置参数。

---

## 🔧 基础配置

### 启用动态爬虫

```bash
DYNAMIC_CRAWLER_ENABLED=true
```

默认值：`true`。设为 `false` 禁用此功能。

---

## 🎯 启发式检测配置

这些参数控制第一层（启发式）检测的行为。

### `HEURISTIC_CONFIDENCE_THRESHOLD`

**说明**：置信度阈值（0-1）。低于此阈值的数据将被标记为"可疑"。

**默认值**：`0.5`

**示例**：
```bash
HEURISTIC_CONFIDENCE_THRESHOLD=0.6  # 要求更高的置信度
```

**影响**：
- 值越高 → 更严格，可疑数据更多，但精准度更高
- 值越低 → 更宽松，接受更多数据，但可能包含错误

---

### `MIN_EXTRACTION_COUNT`

**说明**：页面最少应提取的 IP 数。低于此数字的页面被认为"覆盖率不足"。

**默认值**：`3`

**示例**：
```bash
MIN_EXTRACTION_COUNT=5
```

---

### `ENABLE_STRUCT_AWARE_PARSING`

**说明**：是否启用结构感知解析（识别表格、列表、JSON）。

**默认值**：`true`

**可选值**：`true` 或 `false`

---

## 📄 分页配置

### `MAX_PAGES`

**说明**：最多爬取的页数。`0` 表示无限制。

**默认值**：`5`

**示例**：
```bash
MAX_PAGES=10        # 最多爬取 10 页
MAX_PAGES=0         # 无限制，爱爬多少爬多少（需谨慎）
```

⚠️ **注意**：无限制爬取可能导致长时间运行和高成本。

---

### `MAX_PAGES_NO_NEW_IP`

**说明**：连续多少页无新 IP 时停止爬取。

**默认值**：`3`

**示例**：
```bash
MAX_PAGES_NO_NEW_IP=5
```

**工作原理**：
- 爬取第 1 页，得到 50 个 IP
- 爬取第 2 页，得到新 IP（重置计数）
- 爬取第 3 页，无新 IP（计数 +1）
- 爬取第 4 页，无新 IP（计数 +2）
- 爬取第 5 页，无新 IP（计数 +3，达到阈值，停止）

---

### `CROSS_PAGE_DEDUP`

**说明**：是否跨页去重（同一 IP:port 只存储一份）。

**默认值**：`true`

**可选值**：`true` 或 `false`

---

### `PAGE_FETCH_TIMEOUT_SECONDS`

**说明**：单页获取超时（秒）。

**默认值**：`10`

---

## 🔎 页面接口自动发现配置

当页面本身没有直接出现代理列表时，动态爬虫会尝试从页面和脚本中自动发现 API 端点。

默认流程：
1. 从当前 HTML 中提取候选 URL（只保留可能是 API 的 URL）
2. 下载前 N 个 `<script src>` 并继续提取候选 URL
3. 对候选 URL 应用白名单/黑名单过滤
4. 依次请求前 M 个候选 API，尝试从 JSON 结构中抽取代理字段

### `API_DISCOVERY_ENABLED`

**说明**：是否启用页面脚本接口自动发现。

**默认值**：`true`

**可选值**：`true` 或 `false`

---

### `API_DISCOVERY_MAX_SCRIPTS`

**说明**：最多解析多少个 `script src` 文件用于补充候选 API URL。

**默认值**：`6`

---

### `API_DISCOVERY_MAX_CANDIDATES`

**说明**：最多探测多少个候选 API URL。

**默认值**：`12`

---

### `API_DISCOVERY_RETRIES`

**说明**：单个候选 API 的重试次数（不含首次请求）。

**默认值**：`1`

**说明**：实际总尝试次数 = `API_DISCOVERY_RETRIES + 1`。

---

### `API_DISCOVERY_WHITELIST`

**说明**：候选 URL 白名单关键字（逗号分隔）。

**默认值**：`proxy,ip,/api/,api/,freeagency`

**示例**：
```bash
API_DISCOVERY_WHITELIST=proxy,ip,/api/,freeagency
```

---

### `API_DISCOVERY_BLACKLIST`

**说明**：候选 URL 黑名单关键字（逗号分隔）。

**默认值**：空字符串

**示例**：
```bash
API_DISCOVERY_BLACKLIST=ads,analytics,tracker
```

---

### 接口发现过滤规则说明

- 若白名单非空：候选 URL 必须命中白名单关键字
- 若黑名单非空：候选 URL 只要命中黑名单就会被丢弃
- 当白名单和黑名单同时命中时：黑名单优先（该 URL 会被丢弃）

---

## 🕸️ 运行时接口抓取配置（Playwright XHR/FETCH）

用于处理“接口存在签名/动态 token，静态发现请求拿不到数据”的场景。

触发时机（按代码实现）：
1. 页面常规解析无结果
2. API 自动发现无结果
3. `RUNTIME_API_SNIFF_ENABLED=true`
4. 当前并非 `--render-js` 路径

### `RUNTIME_API_SNIFF_ENABLED`

**说明**：启用 Playwright 运行时网络响应抓取（XHR/FETCH + JSON）。

**默认值**：`false`

**可选值**：`true` 或 `false`

⚠️ **依赖**：需安装 Playwright 与浏览器：
```bash
pip install playwright
python -m playwright install chromium
```

---

### `RUNTIME_API_SNIFF_MAX_PAYLOADS`

**说明**：最多保留多少条 JSON 接口响应。

**默认值**：`20`

---

### `RUNTIME_API_SNIFF_MAX_RESPONSE_BYTES`

**说明**：单条响应文本最大字节数，避免大响应占用过多内存。

**默认值**：`200000`

---

### 运行时抓取补充说明

- 仅捕获 `xhr` / `fetch` 类型且 `content-type` 包含 `json` 的响应
- 若抓到了运行时 JSON，会直接进入代理抽取流程
- 若仅拿到渲染后的 HTML（但未抓到可用 JSON），系统会基于渲染后的 HTML 再尝试一次 API 自动发现

---

## 🤖 LLM 配置

### 启用 AI 辅助

```bash
USE_AI_FALLBACK=false
```

**默认值**：`false`（关闭）

⚠️ **重要**：AI 功能需要用户主动启用，因为需要 API Key 和会产生成本。

---

### LLM 服务配置

#### `LLM_BASE_URL`

**说明**：LLM API 端点 URL。

**默认值**：`https://api.openai.com/v1`

**示例**：

```bash
# OpenAI 官方
LLM_BASE_URL=https://api.openai.com/v1

# Azure OpenAI
LLM_BASE_URL=https://your-resource.openai.azure.com/

# 本地 Ollama
LLM_BASE_URL=http://localhost:11434/v1

# 其他兼容 OpenAI 的服务（如 vLLM）
LLM_BASE_URL=http://localhost:8000/v1
```

---

#### `LLM_MODEL`

**说明**：使用的模型名称。

**默认值**：`gpt-4o-mini`

**建议**：使用较小的模型以降低成本（通常成本是固定的）

**示例**：

```bash
# OpenAI 模型
LLM_MODEL=gpt-4o-mini              # 推荐
LLM_MODEL=gpt-4-turbo
LLM_MODEL=gpt-3.5-turbo

# 其他模型
LLM_MODEL=claude-3-haiku           # Anthropic
LLM_MODEL=llama2                   # Ollama
```

---

#### `LLM_API_KEY`

**说明**：LLM API 密钥。

**默认值**：`sk-your-key-here`（需用户配置）

⚠️ **安全**：
- 切勿提交到 Git（始终在 `.env` 中配置，`.env` 应在 `.gitignore`)
- 使用环境变量或密钥管理服务
- 定期轮换 API Key

**获取方式**：
- **OpenAI**：https://platform.openai.com/api-keys
- **Azure**：Azure Portal → OpenAI 资源 → 密钥
- **其他**：参考对应提供商文档

---

#### `LLM_TIMEOUT_SECONDS`

**说明**：LLM 请求超时（秒）。

**默认值**：`30`

**影响**：
- 值越小 → 更快失败，但可能不允许复杂推理
- 值越大 → 等待更久

---

#### `LLM_MAX_RETRIES`

**说明**：LLM 请求失败时的重试次数。

**默认值**：`3`

---

#### `LLM_SYSTEM_PROMPT`

**说明**：系统提示词，用于约束 LLM 的输出行为。

**默认值**：`你是资深代理数据抽取器。仅输出合法 JSON，不要输出解释、Markdown 或额外文本。`

---

#### `LLM_USER_PROMPT_TEMPLATE`

**说明**：用户提示词模板。

**可用占位符**：`{context_json}`、`{html_snippet}`、`{html}`

**默认值**：当前内置模板（与历史行为一致）。

---

#### `LLM_SUBMIT_FULL_HTML`

**说明**：是否提交完整页面 HTML 给 LLM。

**默认值**：`false`

**可选值**：`true` 或 `false`

---

#### `LLM_HTML_SNIPPET_CHARS`

**说明**：当 `LLM_SUBMIT_FULL_HTML=false` 时，提交给 LLM 的 HTML 字符数。

**默认值**：`5000`

⚠️ **注意**：提交字符越少，提取效果通常越差（上下文不足）。

---

### AI 触发条件

这些参数控制何时调用 AI 辅助。

#### `AI_TRIGGER_ON_LOW_CONFIDENCE`

**说明**：置信度低于阈值时是否触发 AI。

**默认值**：`true`

---

#### `AI_TRIGGER_ON_NO_TABLE`

**说明**：页面无表格时是否触发 AI。

**默认值**：`true`

---

#### `AI_TRIGGER_ON_FAILED_PARSE`

**说明**：解析完全失败时是否触发 AI。

**默认值**：`true`

---

#### `AI_TRIGGER_ON_USER_REQUEST`

**说明**：用户显式请求 AI 时是否触发。

**默认值**：`true`

---

### AI 功能开关

#### `AI_CACHE_ENABLED`

**说明**：是否启用 AI 结果缓存（降低成本）。

**默认值**：`true`

**说明**：相同 HTML 页面的 AI 结果会被缓存，避免重复调用。

---

#### `AI_CACHE_TTL_HOURS`

**说明**：AI 缓存有效期（小时）。

**默认值**：`24`

---

### AI 成本控制

#### `AI_COST_LIMIT_USD`

**说明**：每个爬取任务最多花费的 AI API 成本（美元）。

**默认值**：`100`

**工作原理**：
- 系统跟踪每次 LLM 调用的成本
- 累计成本达到限额时停止调用 AI
- 已提取的数据仍继续处理

**成本估算**：
```
gpt-4o-mini: ~$0.00015 per 1K input tokens
             ~$0.0006 per 1K output tokens

一个 HTML 页面（~50KB）：
- Input tokens: ~12,000
- Output tokens: ~1,000
- Cost: ~$0.002 左右
```

---

## 🛡️ 错误处理配置

### `ERROR_RECOVERY_MODE`

**说明**：页面爬取失败时的恢复策略。

**默认值**：`retry`

**可选值**：
- `retry`：记录失败页面，下次运行时重试
- `skip`：跳过失败页面，继续爬取下一页

**示例**：
```bash
ERROR_RECOVERY_MODE=retry   # 避免丢失数据
ERROR_RECOVERY_MODE=skip    # 快速完成爬取
```

---

### `MAX_RETRIES_PER_PAGE`

**说明**：单页最多重试次数。

**默认值**：`3`

---

### `RETRY_BACKOFF_SECONDS`

**说明**：重试之间的延迟（秒）。

**默认值**：`5`

**说明**：使用固定延迟（不是指数退避）避免过快重试。

---

### `SAVE_FAILED_PAGES_SNAPSHOT`

**说明**：是否保存失败页面的 HTML 快照用于调试。

**默认值**：`true`

---

## 🔍 审查队列配置

### `REQUIRE_MANUAL_REVIEW`

**说明**：是否要求人工审查所有低置信度数据。

**默认值**：`false`

**影响**：
- `true`：低置信度数据不直接入库，需审查
- `false`：低置信度数据有标记地存储，但仍入库

---

### `SAVE_LOW_CONFIDENCE_DATA`

**说明**：是否保存低置信度数据到待审查队列。

**默认值**：`true`

---

### `LOW_CONFIDENCE_THRESHOLD`

**说明**：判定"低置信度"的阈值。

**默认值**：`0.5`

---

## 📊 日志配置

### `DYNAMIC_CRAWLER_LOG_LEVEL`

**说明**：动态爬虫的日志级别。

**默认值**：`INFO`

**可选值**：`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**示例**：
```bash
DYNAMIC_CRAWLER_LOG_LEVEL=DEBUG    # 调试信息更详细
```

---

## 📕 完整配置示例

### 典型场景 1：精准度优先

```bash
# 启用所有检查，使用 AI 辅助
DYNAMIC_CRAWLER_ENABLED=true
HEURISTIC_CONFIDENCE_THRESHOLD=0.7
MIN_EXTRACTION_COUNT=5
USE_AI_FALLBACK=true
AI_TRIGGER_ON_LOW_CONFIDENCE=true
AI_TRIGGER_ON_NO_TABLE=true
MAX_PAGES=10
ERROR_RECOVERY_MODE=retry
SAVE_LOW_CONFIDENCE_DATA=true
```

### 典型场景 2：速度优先（不使用 AI）

```bash
DYNAMIC_CRAWLER_ENABLED=true
HEURISTIC_CONFIDENCE_THRESHOLD=0.4
MIN_EXTRACTION_COUNT=1
USE_AI_FALLBACK=false
API_DISCOVERY_ENABLED=true
RUNTIME_API_SNIFF_ENABLED=false
MAX_PAGES=5
MAX_PAGES_NO_NEW_IP=2
ERROR_RECOVERY_MODE=skip
```

### 典型场景 3：成本控制

```bash
USE_AI_FALLBACK=true
AI_CACHE_ENABLED=true
AI_CACHE_TTL_HOURS=48
AI_COST_LIMIT_USD=50
AI_TRIGGER_ON_LOW_CONFIDENCE=false    # 仅在特定情况使用 AI
AI_TRIGGER_ON_NO_TABLE=true
```

### 典型场景 4：动态接口优先（推荐用于 JS 站点）

```bash
DYNAMIC_CRAWLER_ENABLED=true
API_DISCOVERY_ENABLED=true
API_DISCOVERY_MAX_SCRIPTS=8
API_DISCOVERY_MAX_CANDIDATES=20
API_DISCOVERY_RETRIES=2
API_DISCOVERY_WHITELIST=proxy,ip,/api/,freeagency
API_DISCOVERY_BLACKLIST=ads,analytics,tracker
RUNTIME_API_SNIFF_ENABLED=true
RUNTIME_API_SNIFF_MAX_PAYLOADS=30
RUNTIME_API_SNIFF_MAX_RESPONSE_BYTES=300000
```

---

## 🔗 相关文档

- [通用动态爬虫使用指南](./UNIVERSAL_CRAWLER_USAGE.md)
- [LLM 集成指南](./LLM_INTEGRATION.md)
- [CLI 参考](./CLI_REFERENCE.md)
- [故障排查](./TROUBLESHOOTING.md)
