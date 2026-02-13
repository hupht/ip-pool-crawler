# IP Pool Crawler

智能代理 IP 爬虫系统，支持自动爬取任意公开代理网站，采用 AI 辅助解析、智能分页检测、通用数据提取等先进技术，数据存储于 MySQL，并维护高速 Redis 代理池。

**English**: Intelligent proxy crawler with AI-powered parsing, automatic pagination detection, and universal data extraction. Stores history in MySQL and maintains a fast pool in Redis.

---

## ✨ 核心特性

🤖 **AI 辅助解析** - LLM 智能识别复杂页面结构  
🔄 **智能分页检测** - 自动识别并爬取多页代理列表  
🎯 **通用数据提取** - 支持表格、JSON、列表等多种格式  
🛡️ **多层验证系统** - IP 格式、私网检测、TCP 连接测试  
📊 **完整审计日志** - 记录所有操作，支持故障排查  
⚡ **高性能架构** - 并发抓取、批量验证、Redis 缓存  
🔧 **自动初始化** - 首次运行自动创建数据库和表  
💻 **友好命令行** - 简洁易用的 CLI 工具

---

## 📚 完整文档

所有文档已整理到 `docs/` 文件夹：

| 文档 | 说明 |
|------|------|
| [**INDEX.md**](./docs/INDEX.md) | 📍 文档总导航（推荐首先查看） |
| [**QUICK_START.md**](./docs/QUICK_START.md) | 🚀 3步快速开始 |
| [**FEATURES.md**](./docs/FEATURES.md) | ⭐ 功能详细说明（新） |
| [**MODULES.md**](./docs/MODULES.md) | 📦 模块详细文档（新） |
| [**DEPLOYMENT.md**](./docs/DEPLOYMENT.md) | 🔧 生产部署指南 |
| [**CLI_REFERENCE.md**](./docs/CLI_REFERENCE.md) | 💻 命令行参考 |
| [**API_SERVER.md**](./docs/API_SERVER.md) | 🌐 REST API 服务器（新） |
| [**ARCHITECTURE.md**](./docs/ARCHITECTURE.md) | 🏗️ 系统架构设计 |
| [**AUDIT_LOGGING.md**](./docs/AUDIT_LOGGING.md) | 📊 审计日志系统 |
| [**TROUBLESHOOTING.md**](./docs/TROUBLESHOOTING.md) | 🆘 故障排查 |
| [**UNIVERSAL_CRAWLER_USAGE.md**](./docs/UNIVERSAL_CRAWLER_USAGE.md) | 🌐 动态爬虫使用指南 |
| [**UNIVERSAL_CRAWLER_CONFIG.md**](./docs/UNIVERSAL_CRAWLER_CONFIG.md) | ⚙️ 动态爬虫配置 |
| [**LLM_INTEGRATION.md**](./docs/LLM_INTEGRATION.md) | 🤖 AI 集成指南 |
| [**UNIVERSAL_CRAWLER_API.md**](./docs/UNIVERSAL_CRAWLER_API.md) | 🔌 API 集成文档 |

---

## ⚡ 快速 3 步

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 .env
cp .env.example .env
# 编辑 .env 填入 MySQL 和 Redis 信息

# 3. 运行
python cli.py run
```

**首次自动初始化数据库和表，无需手动 SQL！**

---

## 🎯 常用命令

### 基础命令
```bash
python cli.py run              # 运行完整爬取流程（所有预设源）
python cli.py check            # 批量检查代理可用性
python cli.py get-proxy        # 从池中获取推荐代理
python cli.py verify-deploy    # 验证系统部署
python cli.py --help           # 查看所有命令
```

### 🆕 动态爬虫（NEW）
```bash
# 自动爬取任意代理网站
python cli.py crawl-custom https://example.com/proxies

# 支持多页爬取
python cli.py crawl-custom https://example.com/proxies --max-pages 5

# 启用 AI 辅助解析
python cli.py crawl-custom https://example.com/proxies --use-ai

# 前端渲染站点（Playwright）
python cli.py crawl-custom https://www.iproyal.net/freeagency --render-js --max-pages 2 --no-store --verbose

# 仅测试，不存储
python cli.py crawl-custom https://example.com/proxies --no-store --verbose

# 导出结果到文件
python cli.py crawl-custom https://example.com/proxies --output-json result.json
python cli.py crawl-custom https://example.com/proxies --output-csv result.csv

# 首次启用 render-js
pip install playwright
python -m playwright install chromium
```

### 🌐 API 服务器（NEW）
```bash
# 启动 REST API 服务器（使用 .env 配置，默认 0.0.0.0:8000）
python cli.py server

# 自定义端口（覆盖配置文件）
python cli.py server --port 8080

# 自定义主机和端口
python cli.py server --host 127.0.0.1 --port 9000

# 在 .env 中配置服务器（推荐）
# API_HOST=0.0.0.0
# API_PORT=8000

# 访问 API 文档
# http://localhost:8000/docs

# 使用示例
curl "http://localhost:8000/api/v1/get-proxy?count=5&min_score=80"
curl -X POST "http://localhost:8000/api/v1/crawl-custom" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/proxies", "max_pages": 3}'

# 测试客户端
python tests/test_api_server.py
```

### 诊断工具
```bash
python cli.py diagnose-pipeline   # 诊断完整流程
python cli.py diagnose-sources    # 诊断数据源
python cli.py diagnose-html <url> # 诊断HTML解析
python cli.py redis-ping          # 测试Redis连接
python cli.py check-docs-links    # 校验 docs 链接和锚点（本地/CI 可用）
```

---

## 📁 关键文件和目录

### 入口和工具
- [`cli.py`](./cli.py) - 统一命令行入口
- [`main.py`](./main.py) - 传统爬取流程入口
- [`verify_deploy.py`](./verify_deploy.py) - 部署验证工具
- [`verify_system.py`](./verify_system.py) - 系统验证工具

### 核心模块 (`crawler/`)
- [`dynamic_crawler.py`](./crawler/dynamic_crawler.py) - 🆕 动态爬虫引擎
- [`pipeline.py`](./crawler/pipeline.py) - 传统爬虫流水线
- [`universal_parser.py`](./crawler/universal_parser.py) - 🆕 通用数据解析器
- [`structure_analyzer.py`](./crawler/structure_analyzer.py) - 🆕 HTML 结构分析器
- [`pagination_detector.py`](./crawler/pagination_detector.py) - 🆕 智能分页检测
- [`pagination_controller.py`](./crawler/pagination_controller.py) - 🆕 分页控制器
- [`llm_caller.py`](./crawler/llm_caller.py) - 🆕 LLM API 调用
- [`llm_cache.py`](./crawler/llm_cache.py) - 🆕 LLM 结果缓存
- [`llm_config.py`](./crawler/llm_config.py) - 🆕 LLM 配置管理
- [`proxy_validator.py`](./crawler/proxy_validator.py) - 🆕 代理验证器
- [`http_validator.py`](./crawler/http_validator.py) - 🆕 HTTP 验证器
- [`error_handler.py`](./crawler/error_handler.py) - 🆕 智能错误处理
- [`storage.py`](./crawler/storage.py) - MySQL/Redis 存储
- [`fetcher.py`](./crawler/fetcher.py) - HTTP 抓取
- [`parsers.py`](./crawler/parsers.py) - 传统格式解析器
- [`validator.py`](./crawler/validator.py) - TCP 验证
- [`checker.py`](./crawler/checker.py) - 失败窗口管理
- [`proxy_picker.py`](./crawler/proxy_picker.py) - 代理选取
- [`sources.py`](./crawler/sources.py) - 预设数据源
- [`config.py`](./crawler/config.py) - 配置管理
- [`runtime.py`](./crawler/runtime.py) - 运行时工具

### 其他目录
- [`sql/`](./sql/) - 数据库 Schema 和迁移脚本
- [`tests/`](./tests/) - 完整单元测试套件
- [`docs/`](./docs/) - 📍 完整项目文档
- [`tools/`](./tools/) - 辅助工具脚本
- `logs/` - 运行日志
- `reports/` - 验证报告

---

## 🆘 需要帮助？

**直接查看 docs/ 文件夹中的文档：**

- 第一次用？→ 看 [QUICK_START.md](./docs/QUICK_START.md)
- 使用 API 服务器？→ 看 [API_QUICK_START.md](./docs/API_QUICK_START.md) 或 [API_SERVER.md](./docs/API_SERVER.md)
- 配置 API 端口？→ 看 [API_SERVER_CONFIG.md](./docs/API_SERVER_CONFIG.md)
- 使用动态爬虫？→ 看 [UNIVERSAL_CRAWLER_USAGE.md](./docs/UNIVERSAL_CRAWLER_USAGE.md)
- 配置 AI 辅助？→ 看 [LLM_INTEGRATION.md](./docs/LLM_INTEGRATION.md)
- 想部署？→ 看 [DEPLOYMENT.md](./docs/DEPLOYMENT.md)
- 要理解架构？→ 看 [ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- 了解所有功能？→ 看 [FEATURES.md](./docs/FEATURES.md)
- 模块详解？→ 看 [MODULES.md](./docs/MODULES.md)
- 遇到问题？→ 看 [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)
- 不知道从哪开始？→ 看 [INDEX.md](./docs/INDEX.md)

**推荐阅读顺序（新用户）**：
1. [QUICK_START.md](./docs/QUICK_START.md)
2. [CLI_REFERENCE.md](./docs/CLI_REFERENCE.md)
3. [UNIVERSAL_CRAWLER_USAGE.md](./docs/UNIVERSAL_CRAWLER_USAGE.md)
4. [AUDIT_LOGGING.md](./docs/AUDIT_LOGGING.md)

---

## 🔥 技术亮点

### 1. AI 驱动的智能解析
- 使用 LLM (GPT-4o-mini/GPT-4-turbo) 自动解析复杂页面
- 支持 `.env` 自定义系统提示词/用户提示词模板
- 支持配置提交完整 HTML 或仅提交前 N 字符
- 智能结构识别（表格、JSON、列表、纯文本）
- 置信度评估和低质量数据过滤
- LRU 缓存减少 API 调用成本

### 2. 通用爬虫引擎
- 无需预先配置即可爬取任意代理网站
- 自动检测分页模式（参数、偏移量、rel 标签等）
- 智能停止策略（连续无新 IP 则停止）
- 支持最多 100 页深度爬取

### 3. 多层数据验证
- **格式验证**：IP 地址、端口号格式检查
- **语义验证**：私网 IP、保留地址、广播地址过滤
- **连接验证**：TCP 握手测试
- **HTTP 验证**：实际 HTTP 请求测试（可选）
- **异常检测**：重复代理、可疑端口、异常模式识别

### 4. 完整审计系统
- 记录所有 HTTP 请求、数据库操作、流水线事件
- 支持按时间、模块、错误级别查询
- 性能指标监控（延迟、吞吐量）
- 成本跟踪（LLM API 调用费用）

### 5. 高可用性设计
- 自动数据库初始化和 Schema 迁移
- 失败窗口机制（可配置失败容忍度）
- 软删除机制（代理重现自动恢复）
- 并发控制和错误隔离

---

**🚀 准备好开始了吗？点击这里开始搭建你的IP池吧！ [QUICK_START](./docs/QUICK_START.md)**
