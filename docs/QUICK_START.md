# 快速开始 - 3 步部署

如果你有一台新电脑，已装有 **Python 3.10+** 和 **MySQL + Redis** 服务，按以下步骤 3 分钟内即可运行项目。

## 前置要求

- ✅ Python 3.10+
- ✅ MySQL 5.7+（服务正在运行）
- ✅ Redis 3.0+（服务正在运行）
- ✅ 网络连接（能访问代理源）

## 🚀 三步启动

### 步骤 1️⃣ 安装依赖

```bash
cd ip-pool-crawler
pip install -r requirements.txt
```

**安装的核心库**：
- `requests` - HTTP 请求
- `beautifulsoup4` - HTML 解析
- `pymysql` - MySQL 驱动
- `redis` - Redis 客户端
- `python-dotenv` - 环境变量管理
- `pytest` - 测试框架

### 步骤 2️⃣ 配置连接

复制 [`.env.example`](../.env.example) 为 `.env`，填入你的数据库信息:
python cli.py check-docs-links  # 检查所有文档中的链接是否有效
```bash
# Linux/Mac
cp .env.example .env
copy .env.example .env
```

然后编辑 `.env` 文件，填入 MySQL 和 Redis 信息：

```dotenv
# MySQL 连接
MYSQL_HOST=127.0.0.1        # MySQL 服务器地址，本地使用 127.0.0.1 或 localhost
MYSQL_PORT=3306             # MySQL 端口，默认 3306
MYSQL_USER=root             # MySQL 用户名，建议生产环境使用专用账号
MYSQL_PASSWORD=your_pwd     # MySQL 密码，替换为实际密码
MYSQL_DATABASE=ip_pool      # 数据库名（如不存在会自动创建）

# Redis 连接
REDIS_HOST=127.0.0.1        # Redis 服务器地址，本地使用 127.0.0.1
REDIS_PORT=6379             # Redis 端口，默认 6379
REDIS_PASSWORD=             # Redis 密码（若 Redis 未设密码则留空）

# 日志配置（可选，有默认值）
LOG_LEVEL=INFO              # 日志级别：DEBUG|INFO|WARNING|ERROR，推荐 INFO
LOG_FILE_PATH=./logs/audit.log  # 日志文件路径，相对于项目根目录
LOG_DB_WRITE_ENABLED=true   # 是否将日志写入数据库（audit_logs 表）
LOG_DB_MASK_SENSITIVE=true  # 是否脱敏敏感信息（IP、密码等）
```

**✨ 特别说明**：
- 数据库和表 **会自动创建**，无需手动执行 SQL
- 敏感信息（密码、IP）会被 **自动脱敏** 存储在日志中
- 多个 MySQL/Redis 实例可配置不同 `MYSQL_DATABASE`

### 步骤 3️⃣ 运行爬虫

```bash
python cli.py run
```

**自动完成的事项**：
- ✅ 创建 MySQL 数据库（如不存在）
- ✅ 创建数据表（如不存在）
- ✅ 从 5 个代理源获取代理列表
- ✅ 解析和入库到 MySQL
- ✅ TCP 验证代理可用性
- ✅ 写入 Redis 快速池
- ✅ 记录操作日志

**运行时间**：约 1-3 分钟（取决于网络速度）

---

## 🆕 快速体验动态爬虫

动态爬虫可以自动爬取任意代理网站，无需预先配置：

```bash
# 示例 1: 爬取单个网站（测试模式，不存储到数据库）
python cli.py crawl-custom https://example.com/proxy \
  --no-store \      # 不存储到数据库，仅输出结果（用于测试）
  --verbose         # 显示详细日志（包括抓取和解析过程）

# 示例 2: 正式爬取并存储到数据库
python cli.py crawl-custom https://example.com/proxy \
  --max-pages 3     # 最多爬取 3 页（防止无限爬取）

# 示例 3: 前端渲染站点（JavaScript 动态加载的页面）
python cli.py crawl-custom https://www.iproyal.net/freeagency \
  --render-js \     # 启用 JavaScript 渲染（需安装 playwright）
  --max-pages 2 \   # 最多爬取 2 页
  --no-store \      # 不存储（仅测试）
  --verbose         # 显示详细日志
```

**自动完成的事项**：
- ✅ 自动检测页面结构（表格、JSON、列表）
- ✅ 自动识别分页链接
- ✅ 智能数据提取和验证
- ✅ 创建会话记录（可追溯）

**可选：启用 AI 辅助**（需配置 LLM）：
```bash
# 复杂页面使用 AI 辅助解析
python cli.py crawl-custom https://complex-site.com \
  --use-ai \        # 启用 AI 辅助解析（需配置 .env 中的 LLM_* 参数）
  --max-pages 3     # 最多爬取 3 页（AI 调用有成本，建议限制页数）
```

**可选：自定义 LLM 提示词与提交策略**（在 `.env` 中配置）：
```bash
# 自定义系统提示词（定义 AI 角色和行为）
LLM_SYSTEM_PROMPT=你是资深代理数据抽取器。仅输出合法 JSON，不要输出解释、Markdown 或额外文本。

# 自定义用户提示词模板（实际任务描述，支持变量：{context_json} 和 {html_snippet}）
LLM_USER_PROMPT_TEMPLATE=任务：从 HTML 中提取代理列表，并严格返回 JSON。\n规则：\n1) 仅提取公网 IPv4，过滤私网/保留地址。\n2) port 必须是 1-65535 的整数。\n3) protocol 统一为 http/https/socks4/socks5，未知时用 http。\n4) confidence 取值 0-1。\n5) 按 ip+port+protocol 去重。\n6) 若未提取到结果，返回 {"proxies":[]}。\n输出要求：仅输出 JSON 对象，格式为 {"proxies":[{"ip":"...","port":8080,"protocol":"http","confidence":0.95}]}。\n上下文：{context_json}\nHTML：\n{html_snippet}

# HTML 提交策略配置
LLM_SUBMIT_FULL_HTML=false      # 是否提交完整 HTML（true=完整，false=仅前 N 字符）
LLM_HTML_SNIPPET_CHARS=5000     # 提交的 HTML 字符数（仅当 SUBMIT_FULL_HTML=false 时生效）
```

⚠️ 说明：提交给 LLM 的字符越少，通常效果越差（上下文不足）。

**首次使用 `--render-js` 前请安装**：
```bash
pip install playwright
python -m playwright install chromium
```

详见：[动态爬虫使用指南](./UNIVERSAL_CRAWLER_USAGE.md)

---

## 🔗 相关文档

- 命令参数总览： [CLI_REFERENCE.md](./CLI_REFERENCE.md)
- 动态爬虫场景： [UNIVERSAL_CRAWLER_USAGE.md](./UNIVERSAL_CRAWLER_USAGE.md)
- 动态爬虫配置： [UNIVERSAL_CRAWLER_CONFIG.md](./UNIVERSAL_CRAWLER_CONFIG.md)
- AI 配置与成本： [LLM_INTEGRATION.md](./LLM_INTEGRATION.md)
- AI 提示词与提交策略： [LLM_INTEGRATION.md](./LLM_INTEGRATION.md)
- 审计日志与查询： [AUDIT_LOGGING.md](./AUDIT_LOGGING.md)
- 故障排查： [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

## ✅ 验证安装

```bash
# 查看 MySQL 中的代理数量
mysql -u root -p -e "SELECT COUNT(*) FROM ip_pool.proxy_ips;"
# -u root: 使用 root 用户登录
# -p: 提示输入密码
# -e: 执行 SQL 语句并退出

# 查看 Redis 中的可用代理数量
redis-cli ZCARD proxy:alive
# ZCARD: 获取有序集合的元素数量
# proxy:alive: Redis 中存储可用代理的键名
```

### ✅ 部署后验证脚本（轻量）

只对每个源抓取 1 条样本，不跑完整爬虫：

```bash
python cli.py verify-deploy  # 验证部署是否正常（轻量级，不完整爬取）
```

### ✅ 文档链接检查（本地 + CI 复用）

校验 `docs/` 下的相对链接和锚点是否有效：

```bash
python cli.py check-docs-links  # 检查所有文档中的链接是否有效
```

说明：
- 无坏链时返回退出码 `0`（所有链接正常）
- 有坏链时返回退出码 `1`（可直接用于 CI 阻断）

输出报告：`reports/verify_report.md`（中英文双语）

**常见未抓取成功原因**：
- 网络不可达 / DNS 解析失败
- 目标站点访问被限制（403/429）
- 超时或 TLS 握手失败
- 站点临时故障或返回空数据

如果出现失败，建议先运行：

```bash
python cli.py diagnose-sources  # 诊断所有代理源的可访问性和响应状态
```

## 📌 常用命令

```bash
# 运行传统爬虫（从预设源获取新代理）
python cli.py run  # 自动从所有已启用的代理源抓取并验证

# 验证代理可用性（批量检查已存储的代理）
python cli.py check  # TCP 连接测试，更新可用性状态

# 获取代理（从 Redis/MySQL 中提取）
python cli.py get-proxy \
  --protocol http \  # 指定协议：http|https|socks4|socks5
  --count 3          # 获取数量，默认 10

# 获取特定国家的代理
python cli.py get-proxy \
  --country US \     # 指定国家代码（ISO 3166-1 alpha-2，如 US|CN|UK）
  --count 10         # 获取 10 个美国代理

# 诊断代理源（检查所有源的可访问性）
python cli.py diagnose-sources  # 输出每个源的 HTTP 状态和响应时间

# 查看运行日志（实时监控）
tail -f ./logs/audit.log  # Linux/Mac 使用 tail -f 实时查看日志
# Windows 可使用: Get-Content ./logs/audit.log -Wait -Tail 50
```

## 🔄 定时运行（推荐）

为了自动保持代理池新鲜，建议定时运行爬虫和验证。

### Linux/Mac (Crontab)

```bash
# 编辑定时任务
crontab -e
```

添加以下定时任务：

```cron
# 每天凌晨 3 点运行爬虫（获取新代理）
0 3 * * * cd /path/to/ip-pool-crawler && python cli.py run >> /tmp/crawler.log 2>&1
# 格式: 分 时 日 月 周
# 0 3 * * *: 每天 3:00 AM
# cd /path/to/ip-pool-crawler: 切换到项目目录
# >> /tmp/crawler.log 2>&1: 将标准输出和错误输出追加到日志文件

# 每 30 分钟验证一次代理（保持代理池新鲜）
*/30 * * * * cd /path/to/ip-pool-crawler && python cli.py check >> /tmp/check.log 2>&1
# */30 * * * *: 每 30 分钟执行一次（0:00, 0:30, 1:00, 1:30...）
```

### Windows (任务计划)

1. 打开"任务计划程序"（Win+R → taskschd.msc）
2. 点击"创建基本任务"
3. 填写参数：
   - **任务名称**：IP Pool Crawler（任务显示名称）
   - **触发器**：每天 3:00 AM（选择"每天"，设置时间为 03:00）
   - **操作**：启动程序
     - 程序/脚本：`C:\Python310\python.exe`（替换为你的 Python 安装路径）
     - 添加参数：`cli.py run`（执行的命令）
     - 起始于（工作目录）：`C:\path\to\ip-pool-crawler`（替换为项目实际路径）

4. 再创建一个任务运行 `cli.py check`
   - 任务名称：IP Pool Checker
   - 触发器：每 30 分钟（选择"按计划"→"每小时"→重复间隔 30 分钟）
   - 其他参数同上，仅将"添加参数"改为 `cli.py check`

## 🐛 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|--------|
| `Connection refused` | MySQL/Redis 未启动 | 检查服务：`systemctl status mysql`、`redis-cli ping` |
| `Access denied for user` | MySQL 密码错误 | 检查 `.env` 中的用户名和密码 |
| `ModuleNotFoundError: requests` | 依赖未安装 | 运行 `pip install -r requirements.txt` |
| `Unknown database 'ip_pool'` | 正常现象（首次） | 程序会自动创建，若多次出现检查 MySQL 权限 |
| 没有获取到代理 | 网络/来源问题 | 运行 `python cli.py diagnose-sources` 检查 |
| Redis 里没有代理 | 验证失败/太严格 | 增加 `.env` 中的 `HTTP_TIMEOUT` 参数 |

## 📊 预期结果

首次运行后，你应该看到：

```
✅ 从 Geonode 获取 648 个代理
✅ 验证后 88 个可用代理写入 Redis
✅ 所有操作记录到数据库日志
```

## 🚨 重要提示

- 🔐 **不要提交 `.env` 文件到版本控制**（包含敏感信息）
- 📍 **第一次运行可能较慢**（需要创建表、验证代理）
- 🌐 **需要网络连接**（访问代理源）
- ⚙️ **定时任务避免重叠运行**（同时运行多个会竞争资源）

## 下一步

- 🏗️ 了解系统架构 → [架构设计](./ARCHITECTURE.md)
- 🔧 生产环境部署 → [部署指南](./DEPLOYMENT.md)
- 📊 监控日志系统 → [审计日志](./AUDIT_LOGGING.md)
- 🆘 遇到问题 → [故障排查](./TROUBLESHOOTING.md)

---

**有问题？** 运行 `python cli.py --help` 查看所有命令选项
