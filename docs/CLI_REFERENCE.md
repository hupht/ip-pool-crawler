# 命令行参考

完整的 CLI 命令文档。

## 概览

```bash
python cli.py <command> [options]
```

所有命令都基于统一的 CLI 入口（[`cli.py`](../cli.py)），支持通过 `--env` 参数指定配置文件。

## 🔄 爬虫命令

### run - 运行完整爬取流程

单次完整抓取：从源获取代理 → 解析 → 入库 → 验证 → 写入 Redis。

```bash
python cli.py run [--quick-test] [--quick-record-limit N] [--env PATH]
```

**参数**：
- `--env` (可选) - `.env` 文件路径，默认为当前目录的 `.env`
- `--quick-test` (可选) - 快速模式：在首个可解析数据源后提前结束
- `--quick-record-limit` (可选) - 快速模式下最多处理多少条记录（默认 `1`）

**例子**：
```bash
# 使用默认配置运行
python cli.py run

# 快速模式：仅做链路可用性验证
python cli.py run --quick-test --quick-record-limit 5

# 使用自定义配置文件
python cli.py run --env /etc/ip-pool.env
```

**输出**：
- 抓取结果（数量、来源等）
- 验证统计（成功、失败数）
- 运行耗时

**典型用途**：
- 定时任务：`0 3 * * * cd /path && python cli.py run`
- 手动测试新源

**预期时间**：1-3 分钟

---

### check - 批量验证代理

验证 MySQL 中标记为存活的代理，更新可用性和失败窗口状态。

```bash
python cli.py check [--env PATH]
```

**参数**：
- `--env` (可选) - 配置文件路径

**例子**：
```bash
python cli.py check

python cli.py check --env dev.env
```

**输出**：
- 检查统计（成功、失败、标记删除数）
- 性能统计（平均延迟、最大/最小延迟）

**配置相关**：
- `CHECK_BATCH_SIZE` - 每批检查数量（默认 1000）
- `CHECK_WORKERS` - 并发验证线程数（默认 20）
- `FAIL_WINDOW_HOURS` - 失败窗口时长（默认 24）
- `FAIL_THRESHOLD` - 标记删除的失败次数阈值（默认 5）

**典型用途**：
- 定期检查：`*/30 * * * * cd /path && python cli.py check`
- 周期性验证池中代理

**预期时间**：1-5 分钟（取决于 CHECK_WORKERS 和代理数量）

---

### crawl-custom - 🆕 抓取自定义 URL（动态爬虫）

对单个目标网址执行动态抓取，支持交互模式和非交互模式。使用通用解析器和智能分页检测，可爬取任意格式的代理网站。

```bash
python cli.py crawl-custom [URL] [--max-pages N] [--use-ai] [--render-js] [--no-store] [--verbose] [--output-json FILE] [--output-csv FILE] [--env PATH]
```

**参数**：
- `URL` (可选) - 目标网址；不提供时进入交互模式
- `--max-pages` (可选) - 最大抓取页数（默认使用 `.env` 中 `MAX_PAGES`，最大100）
- `--use-ai` (可选) - 启用 AI 辅助提取（覆盖 `.env` 中 `USE_AI_FALLBACK`）
- `--render-js` (可选) - 使用 Playwright 渲染页面后再解析（适用于前端渲染站点）
- `--no-store` (可选) - 只抓取和解析，不写入 MySQL（测试模式）
- `--verbose` (可选) - 输出详细统计日志
- `--output-json` (可选) - 将结果导出为 JSON 文件
- `--output-csv` (可选) - 将结果导出为 CSV 文件
- `--env` (可选) - 配置文件路径

**交互模式提示**：
- URL（必填）
- 最大页数（默认从配置）
- 是否启用 AI（默认从配置）
- 是否启用 JS 渲染抓取（Playwright）
- 是否自动存储到 MySQL（默认是）

**例子**：

```bash
# 基础用法：抓取单页
python cli.py crawl-custom https://example.com/proxy

# 多页抓取
python cli.py crawl-custom https://example.com/proxy --max-pages 5 --verbose

# AI 辅助模式（适合复杂页面）
python cli.py crawl-custom https://complex-proxy-site.com --use-ai --max-pages 3

# 测试模式：不存储到数据库
python cli.py crawl-custom https://example.com/proxy --no-store --verbose

# 导出结果到文件
python cli.py crawl-custom https://example.com/proxy --output-json result.json
python cli.py crawl-custom https://example.com/proxy --output-csv result.csv --no-store

# JS 渲染页面（前端动态站点）
python cli.py crawl-custom https://www.iproyal.net/freeagency --render-js --max-pages 2 --no-store --verbose

# 交互模式：逐项输入参数
python cli.py crawl-custom
```

**输出示例**：
```
🕷️ 动态爬虫启动
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
URL: https://example.com/proxy
最大页数: 5
使用AI: ❌
存储到DB: ✅

第 1 页: https://example.com/proxy
  ➤ 提取: 50 条
  ➤ 有效: 48 条
  ➤ AI调用: ❌

第 2 页: https://example.com/proxy?page=2
  ➤ 提取: 50 条
  ➤ 有效: 47 条
  ➤ AI调用: ❌

第 3 页: https://example.com/proxy?page=3
  ➤ 提取: 50 条
  ➤ 有效: 49 条
  ➤ AI调用: ❌

⏹️ 停止爬取：已达最大页数限制

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 爬取完成

📊 统计信息:
  爬取页数: 3
  提取总数: 150
  有效代理: 144
  无效代理: 6
  存储数量: 144
  AI调用次数: 0
  总成本: $0.00
  耗时: 12.3 秒

💾 结果已存储到 MySQL
🔄 开始验证新增代理...
✅ 验证完成: 成功 120, 失败 24
```

**智能特性**：

1. **自动分页检测**：
   - 识别 URL 参数（`?page=1`, `?offset=0`）
   - 检测"下一页"链接
   - 支持 `rel="next"` 标签

2. **通用格式支持**：
   - HTML 表格（自动识别列）
   - JSON 数据块
   - 无序/有序列表
   - 纯文本（正则提取）

3. **AI 辅助解析**（启用 `--use-ai` 时）：
   - 自动识别复杂页面结构
   - 低置信度时触发 AI
   - LRU 缓存减少成本
   - 成本限制保护

4. **智能停止策略**：
   - 达到最大页数限制
   - 连续 N 页无新 IP（可配置）
   - 检测到分页循环

**配置相关**（`.env`）：
```bash
# 动态爬虫开关
DYNAMIC_CRAWLER_ENABLED=true

# 默认最大页数
MAX_PAGES=10

# 连续无新IP时停止
MAX_PAGES_NO_NEW_IP=3

# AI 降级开关
USE_AI_FALLBACK=false

# LLM 配置
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o-mini
LLM_COST_LIMIT_USD=1.0
```

**数据库记录**：
- `crawl_sessions` - 会话记录
- `page_logs` - 每页详细日志
- `llm_call_logs` - AI 调用日志（如使用）
- `review_queue` - 低置信度数据（人工审核）

**注意事项**：
1. 若 `.env` 中 `DYNAMIC_CRAWLER_ENABLED=false`，命令会报错退出
2. 使用 `--no-store` 时不会触发自动验证
3. AI 调用可能产生费用，注意设置成本限制
4. 导出功能支持同时输出 JSON 和 CSV

**典型用途**：
- 快速添加新代理源
- 测试未知格式的代理网站
- 一次性批量获取代理
- 评估网站代理质量

**预期时间**：取决于页数和网络速度，通常 10-60 秒/页

---

## 📦 代理获取命令

### get-proxy - 从池中获取代理

从 Redis 或 MySQL 获取代理，支持按协议、国家过滤。

```bash
python cli.py get-proxy [--protocol PROTO] [--country COUNTRY] [--count N] [--env PATH]
```

**参数**：
- `--protocol` (可选) - 协议，多个用逗号分隔
  - 可选值：`http`, `https`, `socks4`, `socks5`
  - 默认：所有协议
  
- `--country` (可选) - 国家代码（ISO 2 letter）
  - 例如：`US`, `CN`, `RU`, `JP`
  - 默认：所有国家
  
- `--count` (可选) - 返回数量（默认 1）

- `--env` (可选) - 配置文件路径

**例子**：
```bash
# 获取 1 个 HTTP 代理
python cli.py get-proxy

# 获取 5 个 HTTPS 代理
python cli.py get-proxy --protocol https --count 5

# 获取 10 个美国的 HTTP 或 SOCKS5 代理
python cli.py get-proxy --protocol http,socks5 --country US --count 10

# 获取 3 个任意代理
python cli.py get-proxy --count 3
```

**输出格式** (JSON)：
```json
{
  "status": "ok",
  "data": [
    {
      "ip": "192.168.1.1",
      "port": 8080,
      "protocol": "http",
      "country": "US",
      "anonymity": "elite",
      "latency_ms": 120
    },
    ...
  ]
}
```

**错误响应**：
```json
{
  "status": "error",
  "message": "No proxies found matching criteria",
  "data": null
}
```

**选取策略**：
1. 优先从 Redis 快速池获取（O(1) 时间）
2. Redis 为空时从 MySQL 回退
3. 随机或有序选取（可配置）

**典型用途**：
- 应用程序调用：`curl http://localhost:8888/proxy`
- 子进程调用：`proxies=$(python cli.py get-proxy --count 5)`

---

## 🔧 诊断命令

### check-docs-links - 文档链接检查脚本（本地 + CI 复用）

校验 `docs/` 目录中的 Markdown 链接和锚点是否有效：

```bash
python cli.py check-docs-links
```

**CI 用法示例**：
```bash
python cli.py check-docs-links
```

**退出码**：
- `0`：全部通过
- `1`：发现坏链/坏锚点

**输出**：
- `links_checked`：检查的链接数量
- `broken_count`：坏链数量
- `BROKEN ...`：问题明细（文件、目标、原因）

---

### verify-deploy - 部署后验证脚本（轻量）

对每个数据源抓取 1 条样本，验证部署环境与抓取链路是否正常，并输出报告。

```bash
python cli.py verify-deploy [--env PATH]
```

**输出**：
- 报告文件：`reports/verify_report.md`
- 控制台摘要：检查项通过数、数据源通过数
- 报告内容：中英文双语

**常见未抓取成功原因**：
- 网络不可达 / DNS 解析失败
- 目标站点限制访问（403/429）
- 超时或 TLS 握手失败
- 站点临时故障或返回空数据

### diagnose-sources - 诊断数据源

检查代理源的可访问性、响应时间、数据大小。

```bash
python cli.py diagnose-sources [--env PATH]
```

**参数**：
- `--env` (可选) - 配置文件路径

**例子**：
```bash
python cli.py diagnose-sources
```

**输出示例**：
```
检诊数据源...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[✓] geonode ..................... 200 (234.5KB) 523ms
[✓] proxy-list-download-http ...... 200 (56.2KB) 312ms
[✓] proxy-list-download-https ..... 200 (48.9KB) 289ms
[✓] proxy-list-download-socks4 ... 200 (102.3KB) 445ms
[✗] proxy-list-download-socks5 ... 403 Forbidden 1000ms
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ 4 个源可用
✗ 1 个源不可用
```

**典型用途**：
- 快速检查数据源可用性
- 网络故障排查
- 确保 Internet 连接正常

---

### diagnose-pipeline - 诊断完整流程

获取所有源的数据，并尝试解析，查看是否有结果。

```bash
python cli.py diagnose-pipeline [--env PATH]
```

**参数**：
- `--env` (可选) - 配置文件路径

**例子**：
```bash
python cli.py diagnose-pipeline
```

**输出示例**：
```
诊断完整流程...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
源: geonode
  状态: ✓ 可用
  大小: 45.2KB
  耗时: 523ms
  解析结果: 234 条记录
  ✓ 协议: http(28), https(45), socks4(89), socks5(72)

源: proxy-list-download-http
  状态: ✓ 可用
  大小: 23.5KB
  耗时: 312ms
  解析结果: 89 条记录
  ✓ 协议: http(89)

源: proxy-list-download-https
  状态: ✓ 可用
  大小: 19.8KB
  耗时: 289ms
  解析结果: 56 条记录
  ✓ 协议: https(56)

总计: 379 条代理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**典型用途**：
- 检查数据源是否能解析
- 了解当前可获取代理的数量
- 评估数据源质量

---

### diagnose-html - 诊断 HTML 解析

检查 HTML 反爬迹象，帮助调试 HTML 源的解析问题。

```bash
python cli.py diagnose-html [--env PATH]
```

**参数**：
- `--env` (可选) - 配置文件路径

**例子**：
```bash
python cli.py diagnose-html
```

**输出示例**：
```
诊断 HTML 解析...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
URL: https://free-proxy-list.com
  HTML 大小: 234.5KB
  元素检测:
    ✓ <table> 表格: 1 个
    ✓ <tr> 行: 500 行
    ✓ <td> 单元格: 3000 个
  反爬检测:
    [⚠] JavaScript 加载: 可能需要浏览器
    [⚠] 验证码: 检测到 reCAPTCHA
    [ℹ] User-Agent 检查: 无
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**典型用途**：
- 调试 HTML 解析器
- 检查源是否被反爬保护
- 协助开发新的 HTML 格式支持

---

### redis-ping - 测试 Redis 连接

简单的 Redis 连通性测试。

```bash
python cli.py redis-ping [--env PATH]
```

**参数**：
- `--env` (可选) - 配置文件路径

**例子**：
```bash
python cli.py redis-ping
```

**成功输出**：
```json
{
  "status": "ok",
  "message": "PONG",
  "redis_info": {
    "redis_version": "6.2.5",
    "used_memory": "12.5M",
    "connected_clients": 5
  }
}
```

**失败输出**：
```json
{
  "status": "error",
  "message": "Connection refused - Redis not running",
  "data": null
}
```

**典型用途**：
- 验证 Redis 连接配置
- 快速检查 Redis 服务状态
- 故障排查

---

## 📊 使用示例

### 完整工作流

```bash
# 1. 检查环境
python cli.py diagnose-sources
python cli.py redis-ping

# 2. 首次运行爬虫
python cli.py run

# 3. 检查代理
python cli.py check

# 4. 获取代理进行测试
python cli.py get-proxy --protocol http --count 5
```

### 定时任务脚本

```bash
#!/bin/bash
WORK_DIR="/path/to/ip-pool-crawler"
LOG_DIR="/var/log/ip-crawler"

# 爬虫任务（每天 3 点）
0 3 * * * cd $WORK_DIR && python cli.py run >> $LOG_DIR/run.log 2>&1

# 检查任务（每 30 分钟）
*/30 * * * * cd $WORK_DIR && python cli.py check >> $LOG_DIR/check.log 2>&1

# 诊断任务（每周一 9 点）
0 9 * * 1 cd $WORK_DIR && python cli.py diagnose-pipeline >> $LOG_DIR/diagnose.log 2>&1
```

### 应用集成

```python
import subprocess
import json

# 获取代理
result = subprocess.run(
    ["python", "cli.py", "get-proxy", "--protocol", "http", "--count", "1"],
    capture_output=True,
    text=True
)

proxy_data = json.loads(result.stdout)
if proxy_data["status"] == "ok":
    proxy = proxy_data["data"][0]
    print(f"IP: {proxy['ip']}, Port: {proxy['port']}")
```

---

## 🚨 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| `Unknown command` | 命令名错误 | 检查拼写，运行 `python cli.py --help` |
| `Connection refused` | MySQL/Redis 未启动 | 检查服务状态 |
| `No proxies found` | 池为空或过滤太严格 | 运行 `python cli.py run` 或调整过滤条件 |
| `JSON decode error` | 输出格式错误 | 检查是否有其他输出混入 |

---

## 💡 最佳实践

1. **定时运行**
   - 爬虫：每 6-12 小时
   - 检查：每 30 分钟
   
2. **错误处理**
   - 重定向输出到日志文件
   - 使用 cron 的邮件通知
   - 监控 exit code

3. **性能优化**
   - 避免同时运行多个任务
   - 根据服务器资源调整 WORKERS
   - 使用连接池回收

4. **监控**
   - 定期检查日志
   - 监控代理池大小
   - 追踪可用率趋势

---

**相关文档**：
- 👉 [快速开始](./QUICK_START.md)
- 👉 [架构设计](./ARCHITECTURE.md)
- 👉 [审计日志](./AUDIT_LOGGING.md)
