# 通用动态爬虫系统 - 分阶段实现计划

> **状态**：A-D 执行清单已完成；阶段明细仍有高阶遗留项（2026-02-13 复核）

**目标**：构建支持任意 URL 自动检测和解析的通用爬虫，包含三层容错机制和可选 AI 辅助。

**总耗时估计**：约 40-50 小时（分 5 个阶段，每阶段 8-10 小时）

---

## ✅ 执行清单（按此清单逐项完成并打勾）

> 说明：后续开发以本清单为唯一进度跟踪入口；每完成一项立即改为 `[x]`。

### A. 已完成（已验证通过）
- [x] A1: `llm_config.py` 完成并有单测（`tests/test_llm_config.py`）
- [x] A2: `universal_detector.py` 完成并有单测
- [x] A3: `structure_analyzer.py` 完成并有单测
- [x] A4: `universal_parser.py` 完成并有单测
- [x] A5: `proxy_validator.py` 完成并有单测
- [x] A6: `pagination_detector.py` 完成并有单测
- [x] A7: HTTP 验证链路已接入 `pipeline`（HTTP 优先，失败回退 TCP）
- [x] A8: `.env.example` 与 `sql/schema.sql` 已包含动态爬虫/LLM相关配置与表结构

### B. 当前最高优先级（P0：先做可用闭环）
- [x] B1: 新增 CLI 命令 `crawl-custom <url>`（非交互模式）
- [x] B2: 新增 `crawl-custom` 交互模式（提示 URL、max-pages、是否启用 AI）
- [x] B3: 创建 `dynamic_crawler.py` 主控制器（单页/多页抓取流程）
- [x] B4: 创建 `pagination_controller.py`（max_pages + no_new_ip 停止策略）
- [x] B5: 将 `DYNAMIC_* / MAX_PAGES_* / PAGE_FETCH_TIMEOUT_SECONDS` 等配置接入运行时
- [x] B6: 新增最小集成测试 `tests/test_dynamic_crawler_integration.py`

### C. 第二优先级（P1：LLM与容错核心）
- [x] C1: 创建 `llm_caller.py`（调用 + JSON解析 + 成本估算）
- [x] C2: 创建 `llm_cache.py`（缓存读写 + TTL）
- [x] C3: 创建 `error_handler.py`（三层容错协调）
- [x] C4: 存储层补齐 session/page_log/review_queue/llm_log 写入方法
- [x] C5: 新增 `tests/test_llm_integration.py`（mock LLM）

### D. 收尾（P2：对齐文档与交付）
- [x] D1: `UNIVERSAL_CRAWLER_USAGE.md` 示例命令与真实 CLI 完全对齐
- [x] D2: `CLI_REFERENCE.md` 增补 `crawl-custom` 与参数说明
- [x] D3: `UNIVERSAL_CRAWLER_API.md` 与实际模块清单一致
- [x] D4: `LLM_INTEGRATION.md` 示例代码与实际 API 保持一致

### 📊 当前进度审计（对照 phase1 + universal 计划）

#### 范围说明（避免歧义）
- A-D 执行清单：用于本轮交付验收，当前为 **23/23（100%）**。
- 下方“阶段分解”是原始长清单，其中部分高阶项未纳入本轮实现，当前作为 backlog 持续推进。

#### 1) 清单完成率
- 已完成：23 / 23
- 总体完成率：100%
- 计算方式：A(8) + B(6) + C(5) + D(4)

#### 2) 分阶段状态
| 阶段 | 目标状态 | 代码现状 | 结论 |
|---|---|---|---|
| 第一阶段 | 完成 | `llm_config/universal_detector/structure_analyzer` + 配置/schema 均已实现 | ✅ 完成 |
| 第二阶段 | 完成 | `universal_parser/proxy_validator/http_validator` 已接入流程并有测试 | ✅ 完成 |
| 第三阶段 | 完成 | `pagination_detector` + `pagination_controller` + 多页流程已实现 | ✅ 完成 |
| 第四阶段 | 完成 | `llm_caller/llm_cache/error_handler` 已实现并有测试 | ✅ 完成 |
| 第五阶段 | 完成 | `crawl-custom` URL/交互模式 + 动态主控制器 + 文档已对齐 | ✅ 完成 |

#### 3) 关键缺口（阶段明细层面，待继续）
- 当前无阻塞性关键缺口（覆盖率目标已达成）

#### 4) 审计依据（代码与测试）
- 模块存在：`llm_config.py`, `universal_detector.py`, `structure_analyzer.py`, `universal_parser.py`, `pagination_detector.py`, `pagination_controller.py`, `proxy_validator.py`, `llm_caller.py`, `llm_cache.py`, `error_handler.py`, `dynamic_crawler.py`
- 测试存在：`test_llm_config.py`, `test_universal_detector.py`, `test_structure_analyzer.py`, `test_universal_parser.py`, `test_proxy_validator.py`, `test_pagination_detector.py`, `test_http_validator.py`, `test_dynamic_crawler_integration.py`, `test_llm_caller.py`, `test_llm_cache.py`, `test_error_handler.py`, `test_llm_integration.py`
- CLI 现状：`crawl-custom` 已支持 URL 模式与交互模式
- 覆盖率证据：`pytest -q tests/test_runtime.py tests/test_validator.py tests/test_pipeline_smoke.py tests/test_dynamic_crawler.py tests/test_dynamic_crawler_integration.py tests/test_pagination_system.py tests/test_pagination_detector.py tests/test_proxy_validator.py tests/test_http_validator.py tests/test_universal_parser.py tests/test_universal_detector.py tests/test_llm_config.py tests/test_llm_caller.py tests/test_llm_cache.py tests/test_error_handler.py tests/test_llm_integration.py tests/test_cli_crawl_custom.py tests/test_result_formatter.py tests/test_storage.py tests/test_schema_extension.py tests/test_schema_auto_init.py tests/test_fetcher.py tests/test_parsers.py tests/test_checker_logic.py tests/test_audit_logging.py --cov=crawler --cov-report=term-missing` => `243 passed`, `TOTAL 80%`

---

## 🗓️ 阶段分解

### 📍 第一阶段：基础架构 + 通用检测器
**预计时间**：8-10 小时  
**目标**：搭建核心模块框架，实现 IP 和端口的基本检测

#### 任务 1.1：创建 LLM 配置模块 (`llm_config.py`)
- [x] 定义 `LLMConfig` dataclass，支持 base_url、model、apikey 等参数
- [x] 实现 `from_env()` 方法读取 `.env` 配置
- [x] 默认使用 OpenAI API 接口
- [x] 支持用户自定义参数覆盖
- [x] 添加参数验证（apikey 不为空、base_url 有效等）
- **测试文件**：`tests/test_llm_config.py`
- **参考**：`crawler/config.py` 的 `Settings` 设计

#### 任务 1.2：创建通用检测器模块 (`universal_detector.py`)
- [x] 定义正则表达式（IP、IP:PORT、协议等）
- [x] 实现 `UniversalDetector` 类，包含方法：
  - `detect_ips(html: str) -> List[IPMatch]`
  - `detect_ports(html: str) -> List[int]`
  - `detect_protocols(html: str) -> List[str]`
  - `detect_ip_port_pairs(html: str) -> List[tuple[str, int]]`
- [x] 返回结构包含：matched_text, position, context (周边 50 个字符)
- [x] 编写单元测试，覆盖多种格式
- **测试用例**：使用 `tests/fixtures/` 中的样本 HTML
- **输出**：检测结果 + 位置信息
- **实现备注**：`detect_ip_port_pairs` 当前返回 `List[IPMatch]`（包含 tuple 信息及额外元数据），语义上覆盖 `ip/port` 需求并增强了可观测性。

#### 任务 1.3：创建结构分析器 (`structure_analyzer.py`)
- [x] 实现表格识别：`find_tables(html: str) -> List[Table]`
  - Table 结构包含：headers, rows, footers
  - 自动猜测列标题（中英文模糊匹配）
- [x] 实现列表识别：`find_lists(html: str) -> List[HTMLList]`
  - 支持 `<ul>/<ol>`, `<div class="list-item">`
- [x] 实现 JSON 检测：`find_json_blocks(html: str) -> List[dict]`
- [x] 实现纯文本检测：`find_text_blocks(html: str) -> List[str]`
- **输出**：结构化容器 + 位置
- **测试**：各种常见网页结构

#### 任务 1.4：修改 `.env.example` + 配置文档
- [x] 添加所有动态爬虫相关的配置参数
- [x] 添加 LLM 配置参数
- [x] 编写配置说明文档
- **文档**：`docs/UNIVERSAL_CRAWLER_CONFIG.md`

#### 任务 1.5：扩展 SQL schema
- [x] 添加 4 张新表：`proxy_review_queue`, `crawl_page_log`, `llm_call_log`, `crawl_session`
- [x] 生成 migration SQL 脚本
- [x] 更新 `sql/schema.sql`
- **文档**：在 schema.sql 中添加注释

---

### 📍 第二阶段：通用解析器 + 验证器
**预计时间**：8-10 小时  
**目标**：实现数据提取、置信度计算、异常检测

#### 任务 2.1：创建通用解析器 (`universal_parser.py`)
- [x] 实现 `UniversalParser` 类
- [x] 方法：`parse(html: str, structure: Structure) -> List[ProxyRecord]`
  - 参数：HTML、检测到的结构、用户提示
  - 返回：IP、port、protocol、anonymity、country 等字段
- [x] 实现多源优先级：表格 > JSON > 纯文本 > 正则匹配
- [x] 实现上下文推理（同行、相邻行查找关联字段）
- [x] 计算置信度（见设计文档算法）
- [x] 处理编码问题（gbk, utf-8, latin-1）
- **返回结构**：包含 confidence, extraction_source 等元数据
- **测试**：多个真实网站的 HTML 样本

#### 任务 2.2：创建验证器 (`validator.py`)
- [x] 实现 `Validator` 类，方法包括：
  - `validate_ip(ip: str) -> bool` - 检查 IP 格式 + 范围
  - `validate_port(port: int) -> bool` - 检查 1-65535
  - `validate_table_structure(table: Table) -> Tuple[bool, str]` - 检查列数异常
  - `validate_page_coverage(records: List[dict], expected: int) -> float` - 覆盖率检查
  - `mark_suspicious_data(record: dict) -> dict` - 标记可疑数据
- [x] 返回验证结果 + 错误原因
- [x] 支持configurable的 threshold
- **测试**：边界情况 + 异常数据

#### 任务 2.3：扩展存储层 (`storage.py` 修改)
- [x] 添加方法：
  - `insert_review_queue_item(data)` - 插入待审查队列
  - `insert_page_log(log)` - 插入爬取日志
  - `insert_llm_call_log(log)` - 插入 LLM 调用记录
  - `insert_crawl_session(session)` - 插入爬取会话
- [x] 添加去重逻辑：`check_duplicate(ip, port) -> bool`
  - 跨页去重（同一爬取会话内）
- [x] 仅修改现有方法的签名，保持向后兼容
- **测试**：集成测试，验证数据正确存储

#### 任务 2.4：编写验证器单元测试
- [x] `tests/test_validator.py`
- [x] 测试各种边界情况
- [x] 至少 80% 代码覆盖率

---

### 📍 第三阶段：分页控制 + 多页支持
**预计时间**：8-10 小时  
**目标**：实现自动分页检测和多页爬取

#### 任务 3.1：创建分页检测器 (`pagination_detector.py`)
- [x] 实现 `PaginationDetector` 类
- [x] 方法 1：URL 参数推断
  - `detect_url_pattern(url: str) -> Optional[URLPattern]`
  - 识别 page=, offset=, start=, p= 等模式
  - 返回模式 + 参数名
- [x] 方法 2：链接检测
  - `find_next_link(html: str) -> Optional[str]`
  - 支持中文："下一页", "下页", "→"
  - 支持英文："next", "next page", "→"
- [x] 方法 3：加载更多按钮
  - `find_load_more(html: str) -> Optional[dict]`
  - 返回按钮所在的 JS 事件信息
- [x] 优先级：URL > 链接 > 加载更多
- **返回**：下一页 URL 或 None
- **测试**：多个分页网站的 HTML 样本

#### 任务 3.2：创建分页控制器 (`pagination_controller.py`)
- [x] 实现 `PaginationController` 类
- [x] 管理分页状态：current_page, visited_urls, ip_count_per_page
- [x] 方法：
  - `should_continue() -> bool` - 判断是否继续
    - 检查 page_count < max_pages
    - 检查是否有新 IP（连续 N 页无新 IP 则停止）
  - `get_next_url() -> Optional[str]` - 获取下一页 URL
  - `record_page_ips(ip_count: int)` - 记录当前页 IP 数
  - `reset()` - 重置状态
- [x] 支持配置参数：max_pages, max_pages_no_new_ip
- **测试**：模拟多页情况

#### 任务 3.3：集成分页到爬虫
- [x] 修改 `dynamic_crawler.py`（稍后创建）
- [x] 在爬取循环中集成 `PaginationController`
- [x] 实现全局去重（跨页）
- [x] 记录每页的爬取日志

#### 任务 3.4：分页系统集成测试
- [x] `tests/test_pagination_system.py`
- [x] 模拟多页爬取场景
- [x] 验证去重、断点记录等功能

**2026-02-13 严格复核补充**
- 已补齐 `find_load_more` 的 JS 事件信息提取（`onclick` / `data-action` / 元素标识）。
- 已新增断点恢复集成测试，验证从 `crawl_page_log.next_page_url` 继续抓取。
- 第三阶段专项回归（含告警即错误）：
  - `python -m pytest tests/test_pagination_detector.py tests/test_pagination_controller.py tests/test_pagination_system.py tests/test_dynamic_crawler.py tests/test_dynamic_crawler_integration.py -q -W error::DeprecationWarning`
  - 结果：`56 passed`

---

### 📍 第四阶段：LLM 辅助 + 容错系统
**预计时间**：10-12 小时  
**目标**：实现 AI 辅助和三层容错机制

#### 任务 4.1：创建 LLM 缓存 (`llm_cache.py`)
- [x] 实现 `LLMCache` 类（可选使用 Redis 或 SQLite）
- [x] 方法：
  - `get(page_hash: str) -> Optional[dict]` - 获取缓存
  - `set(page_hash: str, result: dict, ttl: int)` - 设置缓存
  - `clear_expired()` - 清理过期数据
- [x] 支持配置 TTL（默认 24 小时）
- [x] 降低 AI 成本

#### 任务 4.2：创建 LLM 调用器 (`llm_caller.py`)
- [x] 实现 `LLMCaller` 类
- [x] 方法：
  - `call_llm_for_parsing(html: str, context: dict) -> dict`
    - 构造 structured prompt
    - 指示 LLM 返回 JSON 格式
    - 处理 API 调用（支持 OpenAI + 自定义 base_url）
  - `parse_llm_response(response: str) -> dict` - 解析 JSON 响应
  - `estimate_cost(tokens: int) -> float` - 成本估算
- [x] 错误处理：网络超时、API 限流、JSON 解析错误
- [x] 支持自定义 LLMConfig
- **提示词设计**：见文档附录
- **测试**：Mock LLM 调用（避免真实 API 成本）

#### 任务 4.3：创建容错协调器 (`error_handler.py`)
- [x] 实现三层容错流程
- [x] 第一层：启发式提取
- [x] 第二层：异常检测
  - 调用 `Validator` 检查数据
  - 标记低置信度数据
- [x] 第三层：AI 辅助
  - 判断是否需要调用 LLM
  - 合并 AI 结果
- [x] 方法：
  - `process_page(html, config) -> Tuple[List[dict], List[dict]]`
    - 返回：验证通过的数据 + 待审查数据
  - `handle_extraction_failure()` - 处理提取失败
  - `should_use_ai(reason: str) -> bool` - 判断是否使用 AI
- **测试**：各种失败场景

#### 任务 4.4：创建 LLM 集成测试
- [x] `tests/test_llm_integration.py`
- [x] Mock LLM 响应
- [x] 测试成本控制、缓存、容错流程
- [x] 验证 JSON 响应解析

#### 任务 4.5：编写 LLM 集成文档
- [x] `docs/LLM_INTEGRATION.md`
- [x] 配置说明（base_url, model, apikey）
- [x] 提示词示例
- [x] 成本预估
- [x] 故障排查

**2026-02-13 严格复核补充**
- 已补齐“成本控制”执行闭环：`ErrorHandler` 新增累计成本追踪与 `cost_limit_usd` 超限拦截，超限后返回 `reason=cost_limit_reached` 并跳过 AI 调用。
- 已补齐“第二层异常检测”显式实现：`ErrorHandler` 现接入 `Validator.mark_suspicious_data` 做可疑数据标记，再进入后续验证/审查流。
- 已新增第四阶段缺口测试：
  - `tests/test_error_handler.py`：成本上限拦截、Validator 层调用验证
  - `tests/test_llm_integration.py`：集成链路成本控制阻断
- 第四阶段专项严格回归（含告警即错误）：
  - `python -m pytest tests/test_llm_cache.py tests/test_llm_caller.py tests/test_llm_config.py tests/test_error_handler.py tests/test_llm_integration.py tests/test_dynamic_crawler.py tests/test_dynamic_crawler_integration.py -q -W error::DeprecationWarning`
  - 结果：`45 passed`

---

### 📍 第五阶段：动态爬虫主控制器 + CLI 集成
**预计时间**：10-12 小时  
**目标**：整合所有模块，提供 CLI 接口

#### 任务 5.1：创建动态爬虫主控制器 (`dynamic_crawler.py`)
- [x] 实现 `DynamicCrawler` 类
- [x] 工作流：
  1. 初始化配置 + 创建爬取会话
  2. 获取初始页面
  3. 循环：
     - 检测 IP/结构
     - 解析数据
     - 验证 + 容错
     - 存储
     - 检测下一页
     - 继续或停止
  4. 记录会话统计
- [x] 方法：
  - `crawl(url: str, config: CrawlConfig) -> CrawlResult`
  - `resume_from_checkpoint(session_id: str)` - 断点续爬
  - `get_session_stats(session_id: str) -> dict` - 获取统计
- [x] 支持配置参数
- [x] 完整的日志记录
- **测试**：集成测试，实际爬取一个测试页面

#### 任务 5.2：扩展 CLI (`cli.py` 修改)
- [x] 新增命令：`crawl-custom`
  ```bash
  python cli.py crawl-custom <url> [--max-pages 5] [--use-ai]
  python cli.py crawl-custom  # 交互式模式
  ```
- [x] 实现交互式模式：
  - 提示用户输入 URL
  - 询问是否启用 AI
  - 询问最大页数
  - 显示爬取进度
  - 询问是否保存到 MySQL
- [x] 显示爬取结果统计
- [x] 错误处理和提示
- **参考**：现有 `run` 命令的实现

#### 任务 5.3：创建 CLI 结果展示
- [x] 创建 `cli/result_formatter.py`
- [x] 实现漂亮的表格输出
- [x] 显示爬取统计：
  - 总页数、总 IP 数
  - 平均置信度
  - AI 调用次数 + 成本
  - 待审查数据数量
- [x] 支持导出 CSV/JSON

#### 任务 5.4：集成 TCP 检查流程
- [x] 确保爬到的数据能自动触发 `check_pool.py` 的检查
- [x] 评估 `checker.py`（如需要）：当前实现无需修改 `checker.py`
- [x] 添加测试

#### 任务 5.5：编写使用文档
- [x] `docs/UNIVERSAL_CRAWLER_USAGE.md`
  - 快速开始
  - 命令行示例
  - 交互式模式演示
  - 常见问题
- [x] `docs/TROUBLESHOOTING.md`（添加新部分）
  - [x] AI 相关问题
  - [x] 分页检测失败
  - [x] 数据精准度问题
- [x] 更新 `docs/CLI_REFERENCE.md`

#### 任务 5.6：全面集成测试
- [x] `tests/test_dynamic_crawler_integration.py`
- [x] 实际爬取测试网页
- [x] 验证数据流向完整
- [x] 性能测试（多页爬取耗时）

**2026-02-13 严格复核补充**
- 已补齐交互/详细模式进度展示：`DynamicCrawler.crawl(verbose=True)` 增加开始、逐页抓取、逐页结果日志。
- 已补齐结果导出可用性：`crawl-custom` 新增 `--output-json/--output-csv`，可直接导出抓取结果。
- 已补齐相关测试：
  - `tests/test_dynamic_crawler.py`：逐页进度日志输出验证
  - `tests/test_cli_crawl_custom.py`：导出参数解析与 JSON/CSV 文件导出验证
- 第五阶段专项严格回归（含告警即错误）：
  - `python -m pytest tests/test_dynamic_crawler.py tests/test_dynamic_crawler_integration.py tests/test_cli_crawl_custom.py tests/test_result_formatter.py tests/test_check_pool.py -q -W error::DeprecationWarning`
  - 结果：`28 passed`

---

## 📚 文档清单

需要编写或修改的文档：

| 文档 | 类型 | 时机 |
|------|------|------|
| `2026-02-12-universal-dynamic-crawler-design.md` | 设计 | ✅ 已完成 |
| `2026-02-12-universal-dynamic-crawler-implementation-plan.md` | 计划 | 当前 |
| `docs/UNIVERSAL_CRAWLER_CONFIG.md` | 配置指南 | 第一阶段 |
| `docs/LLM_INTEGRATION.md` | LLM 指南 | 第四阶段 |
| `docs/UNIVERSAL_CRAWLER_USAGE.md` | 使用指南 | 第五阶段 |
| `docs/UNIVERSAL_CRAWLER_API.md` | API 文档 | 第五阶段 |
| `docs/TROUBLESHOOTING.md` | 故障排查 | 第五阶段 |
| `docs/CLI_REFERENCE.md` | CLI 参考 | 第五阶段 |

---

## 🔄 阶段间依赖

```
第一阶段（基础架构）
    ↓
第二阶段（解析 + 验证）
    ↓
第三阶段（分页）
    ↓
第四阶段（LLM + 容错）
    ↓
第五阶段（集成 + CLI）
```

**说明**：各阶段在不破坏现有代码的前提下相对独立，但后续阶段依赖前序阶段的输出。

---

## ✅ 完成标准

每个阶段完成后应满足：

1. **代码**：所有新模块编写完毕，代码覆盖率 > 80%
2. **测试**：所有单元测试通过，集成测试通过
3. **文档**：相关文档已编写
4. **无回归**：现有功能（普通爬虫、检查池等）不受影响
5. **可用性**：阶段成果能独立工作或与现有系统协作

---

## 🧾 最终验收证据（2026-02-13）

- 合并严格回归命令（阶段 1~5，`DeprecationWarning` 视为错误）：
  - `python -m pytest tests/test_universal_detector.py tests/test_structure_analyzer.py tests/test_universal_parser.py tests/test_validator.py tests/test_pagination_detector.py tests/test_pagination_controller.py tests/test_pagination_system.py tests/test_dynamic_crawler.py tests/test_dynamic_crawler_integration.py tests/test_cli_crawl_custom.py tests/test_storage.py tests/test_error_handler.py tests/test_llm_integration.py tests/test_llm_caller.py tests/test_llm_cache.py tests/test_llm_config.py tests/test_result_formatter.py tests/test_check_pool.py -q -W error::DeprecationWarning`
- 结果：`189 passed`。
- 结论：阶段 1~5 在“代码实现 + 主流程生效 + 严格测试”口径下通过验收。

---

## 🚀 快速开始指南（实现时）

对于实现者：

1. **创建 worktree**：`git worktree add ../dynamic-crawler-feature main`
2. **按阶段实现**：逐个完成上述任务
3. **提交规则**：每个任务完成后提交一个 commit
4. **分支**：基于 `main` 创建 PR
5. **测试**：运行 `pytest tests/test_*.py --cov`
6. **代码审查**：提交 PR 后请求审查

---

## 📞 联系与问题

- **问题**：见 `docs/TROUBLESHOOTING.md`
- **设计细节**：见 `2026-02-12-universal-dynamic-crawler-design.md`
- **配置示例**：见 `.env.example`
