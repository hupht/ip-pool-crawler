# 通用动态爬虫 - 使用指南

**版本**：1.0  
**日期**：2026-02-12

---

## 🚀 快速开始

### 1. 最简单的用法

```bash
python cli.py crawl-custom https://example.com/proxy-list
```

系统会：
1. 下载页面 HTML
2. 启发式解析（表格 / JSON / 列表 / 文本）
3. 若无结果，自动尝试页面接口发现（HTML + script）
4. 若仍无结果且已启用运行时 sniff，抓取 XHR/FETCH JSON 响应
5. 自动识别分页并继续抓取
6. 校验、去重并按策略入库
7. 输出本次抓取统计

### 2. 交互式模式

```bash
python cli.py crawl-custom
```

输出示例：
```
欢迎使用通用动态爬虫交互模式

请输入网址: https://example.com/proxy-list
最大页数 [5]: 
启用 AI 辅助 [y/N]: 
启用 JS 渲染抓取(Playwright) [y/N]: 
自动存储到 MySQL [Y/n]: y

开始爬取...

[页面 1/3] 检测 IP...
  ✓ 已提取 45 个 IP
  📄 检测到下一页
  
[页面 2/3] 检测 IP...
  ✓ 已提取 42 个 IP
  📄 检测到下一页

[页面 3/3] 检测 IP...
  ✓ 已提取 38 个 IP
  ⏹️ 没有更多页面

爬取完成！
━━━━━━━━━━━━━━━━━━━━━━━━
总计：3 页，125 个唯一 IP
平均置信度：0.87
待审查：5 条
存储：MySQL ✓
━━━━━━━━━━━━━━━━━━━━━━━━

可按需执行 `python cli.py check` 做批量 TCP 检查。
```

---

## 📋 命令参考

### 基础语法

```bash
python cli.py crawl-custom [URL] [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认 | 示例 |
|------|------|------|------|
| `--max-pages` | 最大页数 | 5 | `--max-pages 10` |
| `--use-ai` | 启用 AI 辅助 | false | `--use-ai` |
| `--render-js` | 使用 Playwright 渲染后解析 | false | `--render-js` |
| `--no-store` | 不存储到 MySQL | false | `--no-store` |
| `--verbose` | 详细日志 | false | `--verbose` |
| `--output-json` | 导出 JSON 结果文件 | 无 | `--output-json result.json` |
| `--output-csv` | 导出 CSV 结果文件 | 无 | `--output-csv result.csv` |

### 自动回退链路（默认）

`crawl-custom` 的解析是分层回退的，不需要新增 CLI 参数：

1. 页面启发式解析（默认）
2. 页面接口自动发现（`API_DISCOVERY_*`）
3. 运行时接口抓取（`RUNTIME_API_SNIFF_*`，需启用且仅在非 `--render-js` 路径）

对应关系：
- `--render-js`：主动走“浏览器渲染 HTML → 解析”路径
- `RUNTIME_API_SNIFF_ENABLED=true`：在非 `--render-js` 且静态链路无结果时，尝试抓取运行时 JSON 响应

推荐起步配置（`.env`）：
```bash
API_DISCOVERY_ENABLED=true
API_DISCOVERY_MAX_SCRIPTS=6
API_DISCOVERY_MAX_CANDIDATES=12
RUNTIME_API_SNIFF_ENABLED=false
```

### 完整示例

```bash
# 爬取最多 10 页，启用 AI，详细日志
python cli.py crawl-custom https://example.com/proxy \
  --max-pages 10 \
  --use-ai \
  --verbose

# 仅检测不存储，置信度要求高
python cli.py crawl-custom https://example.com/proxy \
  --no-store

# 快速爬取
python cli.py crawl-custom https://example.com/proxy \
  --max-pages 3 \
  --verbose

# 前端渲染站点（需 Playwright）
python cli.py crawl-custom https://www.iproyal.net/freeagency \
  --render-js \
  --max-pages 2 \
  --no-store \
  --verbose
```

---

## 🎯 常见场景

### 场景 1：快速测试

**目标**：快速验证一个新的代理网站

```bash
python cli.py crawl-custom https://example.com/proxy \
  --max-pages 1 \
  --no-store \
  --verbose
```

结果：只爬首页，显示检测到的 IP，不存储。

---

### 场景 2：完整爬取 + 人工审查

**目标**：爬取所有页面，但保留低质数据供审查

```bash
# 在 .env 中配置
SAVE_LOW_CONFIDENCE_DATA=true
REQUIRE_MANUAL_REVIEW=true

# 然后爬取
python cli.py crawl-custom https://example.com/proxy --verbose
```

**后续**：
1. 检查 `proxy_review_queue` 表
2. 人工审查数据
3. 执行 SQL 将审查过的数据插入 `proxy` 表

---

### 场景 3：使用 AI 改善新网站

**目标**：为后续 AI 提取流程预留运行参数

**前置条件**：配置 LLM（见 [LLM 集成指南](./LLM_INTEGRATION.md)）

```bash
python cli.py crawl-custom https://newsite.com/proxy \
  --use-ai \
  --verbose
```

输出示例：
```
crawl-custom url=https://newsite.com/proxy pages=3 extracted=120 valid=98 stored=98
```

> 说明：`--use-ai` 参数已接入主流程；当触发条件满足时会调用 LLM 并与启发式结果合并。

---

### 场景 4：导出抓取结果到文件

```bash
python cli.py crawl-custom https://example.com/proxy \
  --max-pages 3 \
  --output-json crawl_result.json \
  --output-csv crawl_result.csv
```

系统会在控制台输出结果，并同时导出 JSON/CSV 供后续分析。

---

### 场景 5：抓取前端渲染站点

```bash
# 首次使用先安装（一次即可）
pip install playwright
python -m playwright install chromium

# 开启 JS 渲染抓取
python cli.py crawl-custom https://www.iproyal.net/freeagency --render-js --no-store --verbose
```

说明：`--render-js` 会先用浏览器渲染页面，再把渲染后的 HTML 交给现有解析流程。

---

### 场景 6：仅采集不入库（干跑）

**目标**：验证页面可解析，但不写 MySQL

```bash
python cli.py crawl-custom https://example.com/proxy \
  --max-pages 2 \
  --no-store \
  --verbose
```

系统会：
1. 正常抓取与解析
2. 显示 extracted/valid 统计
3. 不执行入库

---

### 场景 7：页面无明文代理，自动发现接口

**目标**：页面 HTML 没有直接 IP:Port，但脚本里有 API 端点

```bash
# 在 .env 中建议配置
API_DISCOVERY_ENABLED=true
API_DISCOVERY_MAX_SCRIPTS=8
API_DISCOVERY_MAX_CANDIDATES=20
API_DISCOVERY_WHITELIST=proxy,ip,/api/,freeagency
API_DISCOVERY_BLACKLIST=ads,analytics,tracker

# 执行抓取
python cli.py crawl-custom https://example.com/freeagency \
  --no-store \
  --verbose
```

可能看到日志：
```
crawl-custom api-discovery candidates=12
crawl-custom api-hit url=https://example.com/api/proxy records=50
```

---

### 场景 8：签名/动态 token 接口，启用运行时 sniff 回退

**目标**：静态 API 发现拿不到数据，但浏览器运行时网络里有 JSON 响应

```bash
# 首次使用先安装（一次即可）
pip install playwright
python -m playwright install chromium

# 在 .env 中启用运行时抓取
RUNTIME_API_SNIFF_ENABLED=true
RUNTIME_API_SNIFF_MAX_PAYLOADS=30
RUNTIME_API_SNIFF_MAX_RESPONSE_BYTES=300000

# 执行抓取（注意：此场景建议不要带 --render-js）
python cli.py crawl-custom https://example.com/freeagency \
  --no-store \
  --verbose
```

可能看到日志：
```
crawl-custom runtime-sniff records=50
```

说明：若同时使用 `--render-js`，当前实现不会触发运行时 sniff 回退。

---

## 📊 理解输出

### 爬取过程日志

```
crawl-custom url=https://example.com/proxy pages=3 extracted=125 valid=120 stored=120
```

**含义**：
- **pages**：实际抓取页数
- **extracted**：解析出的候选代理数量
- **valid**：通过校验的代理数量
- **stored**：成功写入 MySQL 的数量（`--no-store` 时为 0）

### 最终统计

```
爬取完成！
━━━━━━━━━━━━━━━━━━━━━━━━
pages=3
extracted=125
valid=120
stored=120
━━━━━━━━━━━━━━━━━━━━━━━━
```

**含义**：
- **extracted**：提取总量（去重前）
- **valid**：格式校验通过且可入库数量
- **stored**：写入数据库数量
- 当未使用 `--no-store` 且有新入库数据时，会自动触发后续 TCP 批量检查

---

## 🔍 查看结果

### 查看已提取的 IP

```bash
# MySQL 中查看
python -c "
from crawler.storage import Storage
storage = Storage.from_env()

# 查看最近爬取的 IP
ips = storage.connection.execute('''
    SELECT ip, port, protocol, protocol, is_available, score
    FROM proxy
    WHERE created_at > DATE_SUB(NOW(), INTERVAL 1 DAY)
    ORDER BY created_at DESC
    LIMIT 20
''').fetchall()

for ip in ips:
    print(ip)
"
```

### 查看待审查数据

```bash
python -c "
from crawler.storage import Storage
storage = Storage.from_env()

# 查看待审查队列
reviews = storage.connection.execute('''
    SELECT id, ip, port, confidence, extraction_method, error_reason
    FROM proxy_review_queue
    WHERE status = 'pending'
    LIMIT 20
''').fetchall()

for review in reviews:
    print(review)
"
```

### 查看爬取日志

```bash
python -c "
from crawler.storage import Storage
storage = Storage.from_env()

# 查看最近的爬取日志
logs = storage.connection.execute('''
    SELECT crawl_session_id, source_url, page_number, ip_count, 
           confidence_avg, error_message
    FROM crawl_page_log
    ORDER BY created_at DESC
    LIMIT 20
''').fetchall()

for log in logs:
    print(log)
"
```

---

## 🛠️ 故障排查

### 问题 1：无法检测 IP

**症状**：爬取完成但 IP 数为 0

**可能原因**：
1. 网页结构不同（表格格式、JSON 等）
2. IP 地址在 JavaScript 生成的内容中
3. 网页需要登录或验证

**解决方案**：

```bash
# 1. 启用详细日志
python cli.py crawl-custom https://example.com/proxy \
  --verbose

# 2. 查看原始 HTML
python -c "
from crawler.fetcher import fetch
html = fetch('https://example.com/proxy')
print(html[:2000])  # 打印前 2000 字符
"

# 3. 使用 AI 辅助
python cli.py crawl-custom https://example.com/proxy \
  --use-ai

# 4. 检查页面是否需要 User-Agent
# 在 .env 中修改
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36

# 5. 启用页面接口自动发现
API_DISCOVERY_ENABLED=true
API_DISCOVERY_WHITELIST=proxy,ip,/api/,freeagency

# 6. 对签名接口启用运行时 sniff（需 Playwright）
RUNTIME_API_SNIFF_ENABLED=true
RUNTIME_API_SNIFF_MAX_PAYLOADS=30
```

### 问题 2：分页检测失败

**症状**：只爬了第 1 页，虽然有更多页面

**可能原因**：
1. 下一页 URL 格式未被识别
2. 分页用 JavaScript 实现

**解决方案**：

```bash
# 1. 手动指定页数或 URL 模式
# 在 .env 中添加
MAX_PAGES=1  # 仅爬首页，再手动分析

# 2. 检查页面中的分页链接
python -c "
from bs4 import BeautifulSoup
from crawler.fetcher import fetch

html = fetch('https://example.com/proxy')
soup = BeautifulSoup(html, 'html.parser')

# 查找所有链接
links = soup.find_all('a')
for link in links:
    if '下一页' in link.text or 'next' in link.text.lower():
        print(f'找到下一页链接: {link.get(\"href\")}')
"

# 3. 使用 JavaScript 渲染（可选，需额外配置）
# 见高级用法
```

### 问题 3：存储失败

**症状**：爬取成功，但数据未入库

**可能原因**：
1. MySQL 连接失败
2. 表不存在
3. 数据格式错误

**解决方案**：

```bash
# 1. 检查 MySQL 连接
python -c "
from crawler.storage import Storage
storage = Storage.from_env()
print('✓ MySQL 连接成功')
"

# 2. 检查表是否存在
python -c "
from crawler.storage import Storage
storage = Storage.from_env()
tables = storage.connection.execute(
    'SHOW TABLES'
).fetchall()
print(tables)
"

# 3. 检查数据格式
python -c "
from crawler.universal_parser import UniversalParser
parser = UniversalParser()
record = parser.parse('<html>1.2.3.4:8080</html>')
print(record)  # 检查返回的数据格式
"
```

---

## 📈 性能优化

### 快速爬取

```bash
# 小页数 + 不入库，用于快速验证
python cli.py crawl-custom https://example.com/proxy \
  --max-pages 5 \
  --no-store
```

### 精准爬取

```bash
# 启用 AI 参数并查看详细日志
python cli.py crawl-custom https://example.com/proxy \
  --use-ai \
  --verbose
```

### 成本控制

```bash
# 禁用 AI（避免成本）
# 在 .env 中
USE_AI_FALLBACK=false

# 或启用 AI 缓存
AI_CACHE_ENABLED=true
AI_CACHE_TTL_HOURS=48
```

---

## 🔗 相关文档

- [配置指南](./UNIVERSAL_CRAWLER_CONFIG.md)
- [LLM 集成指南](./LLM_INTEGRATION.md)
- [API 文档](./UNIVERSAL_CRAWLER_API.md)
- [故障排查](./TROUBLESHOOTING.md)
- [CLI 参考](./CLI_REFERENCE.md)
