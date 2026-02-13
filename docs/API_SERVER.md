# API 服务器使用指南

## 概述

IP代理池爬虫提供了一个基于 FastAPI 的 REST API 服务器，允许前端或其他应用通过 HTTP 请求访问爬虫的核心功能。

## 快速开始

### 1. 安装依赖

```bash
cd ip-pool-crawler
pip install -r requirements.txt
```

### 2. 配置服务器（可选）

在 `.env` 文件中配置 API 服务器：

```bash
# API 服务器配置
API_HOST=0.0.0.0              # 监听地址（0.0.0.0=所有接口，127.0.0.1=仅本地）
API_PORT=8000                 # 监听端口
```

### 3. 启动服务器

```bash
# 默认启动（使用 .env 中的配置，默认 0.0.0.0:8000）
python cli.py server

# 命令行参数会覆盖配置文件
python cli.py server --port 8080
python cli.py server --host 127.0.0.1 --port 9000

# 使用自定义 .env 文件
python cli.py server --env /path/to/.env
```

### 3. 访问 API 文档

服务器启动后，访问以下地址查看交互式 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API 端点

### 系统相关

#### GET /
根路径 - 健康检查

**响应示例**:
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

#### GET /health
健康检查端点

**响应示例**:
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

### 爬虫功能

#### POST /api/v1/crawl-custom
爬取自定义 URL 的代理数据

**请求体**:
```json
{
  "url": "https://www.example.com/proxy-list",
  "max_pages": 3,
  "use_ai": false,
  "render_js": false,
  "no_store": false,
  "verbose": false
}
```

**参数说明**:
- `url` (必填): 目标网页 URL
- `max_pages` (可选): 最大爬取页数，默认 1
- `use_ai` (可选): 是否启用 AI 辅助解析，默认 false
- `render_js` (可选): 是否使用 Playwright 渲染 JS，默认 false
- `no_store` (可选): 是否不存储到 MySQL，默认 false
- `verbose` (可选): 是否输出详细日志，默认 false

**响应示例**:
```json
{
  "success": true,
  "url": "https://www.example.com/proxy-list",
  "session_id": 123,
  "total_ips": 50,
  "stored": 45,
  "avg_confidence": 0.85,
  "ai_calls_count": 2,
  "llm_cost_usd": 0.0015,
  "review_pending_count": 5,
  "error": null
}
```

**cURL 示例**:
```bash
curl -X POST "http://localhost:8000/api/v1/crawl-custom" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.example.com/proxy-list",
    "max_pages": 3,
    "use_ai": true
  }'
```

#### POST /api/v1/run
运行完整的爬虫流程（后台任务）

**请求体**:
```json
{
  "quick_test": false,
  "quick_record_limit": 1
}
```

**参数说明**:
- `quick_test` (可选): 快速测试模式，默认 false
- `quick_record_limit` (可选): 快速模式记录限制，默认 1

**响应示例**:
```json
{
  "success": true,
  "message": "爬虫任务已在后台启动"
}
```

**cURL 示例**:
```bash
curl -X POST "http://localhost:8000/api/v1/run" \
  -H "Content-Type: application/json" \
  -d '{"quick_test": true}'
```

---

### 代理检查

#### POST /api/v1/check
运行 TCP 批量检查（后台任务）

检查数据库中的所有代理，更新其连通性和分数。

**响应示例**:
```json
{
  "success": true,
  "message": "代理检查任务已在后台启动"
}
```

**cURL 示例**:
```bash
curl -X POST "http://localhost:8000/api/v1/check"
```

---

### 代理获取

#### GET /api/v1/get-proxy
从代理池获取代理

**查询参数**:
- `count` (可选): 代理数量，范围 1-1000，默认 1
- `protocol` (可选): 协议类型，如 http, https, socks4, socks5
- `country` (可选): 国家代码，如 US, CN
- `min_score` (可选): 最小分数，范围 0-100

**响应示例**:
```json
{
  "success": true,
  "count": 2,
  "proxies": [
    {
      "ip": "192.168.1.1",
      "port": 8080,
      "protocol": "http",
      "country": "US",
      "score": 95,
      "last_ok": "2026-02-13T10:30:00"
    },
    {
      "ip": "192.168.1.2",
      "port": 3128,
      "protocol": "https",
      "country": "CN",
      "score": 88,
      "last_ok": "2026-02-13T10:25:00"
    }
  ]
}
```

**cURL 示例**:
```bash
# 获取 5 个代理
curl "http://localhost:8000/api/v1/get-proxy?count=5"

# 获取 10 个美国的 HTTP 代理，最小分数 80
curl "http://localhost:8000/api/v1/get-proxy?count=10&protocol=http&country=US&min_score=80"
```

---

### 诊断功能

#### GET /api/v1/diagnose/sources
检查所有原始代理源的可用性

返回每个源的 HTTP 状态和可访问性信息。

**响应示例**:
```json
{
  "success": true,
  "message": "Source 1: OK (200)\nSource 2: Failed (timeout)\n..."
}
```

**cURL 示例**:
```bash
curl "http://localhost:8000/api/v1/diagnose/sources"
```

#### GET /api/v1/diagnose/pipeline
检查数据管道（获取和解析）

测试每个源的数据获取和解析能力。

**响应示例**:
```json
{
  "success": true,
  "message": "Pipeline test results...\n"
}
```

**cURL 示例**:
```bash
curl "http://localhost:8000/api/v1/diagnose/pipeline"
```

---

## JavaScript 前端示例

### 使用 Fetch API

```javascript
// 爬取自定义 URL
async function crawlCustomUrl(url) {
  const response = await fetch('http://localhost:8000/api/v1/crawl-custom', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      url: url,
      max_pages: 3,
      use_ai: true,
    }),
  });
  
  const result = await response.json();
  console.log('爬取结果:', result);
  return result;
}

// 获取代理
async function getProxies(count = 10) {
  const response = await fetch(
    `http://localhost:8000/api/v1/get-proxy?count=${count}&min_score=80`
  );
  
  const result = await response.json();
  console.log('代理列表:', result.proxies);
  return result.proxies;
}

// 运行爬虫
async function runCrawler() {
  const response = await fetch('http://localhost:8000/api/v1/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      quick_test: false,
    }),
  });
  
  const result = await response.json();
  console.log('爬虫状态:', result);
  return result;
}

// 检查代理
async function checkProxies() {
  const response = await fetch('http://localhost:8000/api/v1/check', {
    method: 'POST',
  });
  
  const result = await response.json();
  console.log('检查状态:', result);
  return result;
}
```

### 使用 Axios

```javascript
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

// 爬取自定义 URL
async function crawlCustomUrl(url, options = {}) {
  try {
    const response = await axios.post(`${API_BASE}/api/v1/crawl-custom`, {
      url,
      max_pages: options.maxPages || 1,
      use_ai: options.useAi || false,
      render_js: options.renderJs || false,
      no_store: options.noStore || false,
      verbose: options.verbose || false,
    });
    
    return response.data;
  } catch (error) {
    console.error('爬取失败:', error.response?.data || error.message);
    throw error;
  }
}

// 获取代理
async function getProxies(params = {}) {
  try {
    const response = await axios.get(`${API_BASE}/api/v1/get-proxy`, {
      params: {
        count: params.count || 10,
        protocol: params.protocol,
        country: params.country,
        min_score: params.minScore,
      },
    });
    
    return response.data.proxies;
  } catch (error) {
    console.error('获取代理失败:', error.response?.data || error.message);
    throw error;
  }
}
```

---

## Python 客户端示例

```python
import requests

API_BASE = "http://localhost:8000"

# 爬取自定义 URL
def crawl_custom_url(url, max_pages=1, use_ai=False):
    response = requests.post(
        f"{API_BASE}/api/v1/crawl-custom",
        json={
            "url": url,
            "max_pages": max_pages,
            "use_ai": use_ai,
        }
    )
    response.raise_for_status()
    return response.json()

# 获取代理
def get_proxies(count=10, protocol=None, country=None, min_score=None):
    params = {"count": count}
    if protocol:
        params["protocol"] = protocol
    if country:
        params["country"] = country
    if min_score is not None:
        params["min_score"] = min_score
    
    response = requests.get(
        f"{API_BASE}/api/v1/get-proxy",
        params=params
    )
    response.raise_for_status()
    return response.json()["proxies"]

# 运行爬虫
def run_crawler(quick_test=False):
    response = requests.post(
        f"{API_BASE}/api/v1/run",
        json={"quick_test": quick_test}
    )
    response.raise_for_status()
    return response.json()

# 示例使用
if __name__ == "__main__":
    # 爬取自定义 URL
    result = crawl_custom_url(
        "https://www.example.com/proxy-list",
        max_pages=3,
        use_ai=True
    )
    print(f"爬取成功，获取 {result['total_ips']} 个IP")
    
    # 获取代理
    proxies = get_proxies(count=10, min_score=80)
    for proxy in proxies:
        print(f"{proxy['ip']}:{proxy['port']} - {proxy['protocol']} - 分数:{proxy['score']}")
```

---

## 错误处理

所有 API 端点在发生错误时返回以下格式：

```json
{
  "success": false,
  "error": "错误描述信息"
}
```

HTTP 状态码：
- `200`: 成功
- `400`: 请求参数错误
- `403`: 功能被禁用
- `500`: 服务器内部错误

---

## 配置说明

API 服务器使用与 CLI 相同的配置文件（.env）。确保已正确配置：

### 数据库配置

```bash
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=ip_pool

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 动态爬虫配置
DYNAMIC_CRAWLER_ENABLED=true
MAX_PAGES=5
USE_AI_FALLBACK=false
```

### API 服务器配置

```bash
# API 服务器配置
API_HOST=0.0.0.0              # 监听地址（0.0.0.0=所有接口，127.0.0.1=仅本地）
API_PORT=8000                 # 监听端口（默认 8000）
```

**优先级**：命令行参数 > 配置文件 > 默认值

---

## 安全建议

1. **生产环境**: 不要使用 `0.0.0.0`，改用 `127.0.0.1` 或配置防火墙
2. **认证**: 建议添加 API Key 或 OAuth2 认证
3. **HTTPS**: 生产环境使用 HTTPS（配合 Nginx 或 Caddy）
4. **限流**: 使用 slowapi 或 Nginx 限制请求频率

---

## 性能优化

- 长时间运行的任务（run, check）会在后台执行，不会阻塞 API 响应
- 使用线程池处理阻塞操作
- 建议使用 gunicorn 或 supervisor 管理生产环境进程

启动多进程模式：
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 故障排查

### 服务器无法启动

检查依赖是否安装：
```bash
pip install fastapi uvicorn[standard]
```

### 配置文件错误

确保 .env 文件存在且格式正确：
```bash
python cli.py verify-deploy
```

### 端口被占用

更换端口：
```bash
python cli.py server --port 8080
```

---

## 更多信息

- 查看 CLI 文档: [docs/CLI_REFERENCE.md](CLI_REFERENCE.md)
- 查看架构文档: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- 提交问题: GitHub Issues
