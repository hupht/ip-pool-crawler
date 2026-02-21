# API 服务器快速开始

## 安装依赖

```bash
cd ip-pool-crawler
pip install fastapi "uvicorn[standard]" pydantic
```

或者使用 requirements.txt:

```bash
pip install -r requirements.txt
```

## 配置服务器（可选）

在 `.env` 文件中配置：

```bash
# API 服务器配置
API_HOST=0.0.0.0              # 监听地址
API_PORT=8000                 # 监听端口
```

**说明**：
- `API_HOST=0.0.0.0`: 监听所有网络接口，允许远程访问
- `API_HOST=127.0.0.1`: 仅本地访问，更安全
- 命令行参数会覆盖配置文件

## 启动服务器

```bash
# 默认启动（使用 .env 配置，默认 0.0.0.0:8000）
python cli.py server

# 自定义端口（覆盖配置文件）
python cli.py server --port 9000

# 自定义主机和端口
python cli.py server --host 127.0.0.1 --port 8080
```

启动后你会看到：

```
🚀 启动 IP代理池 API 服务器...
📡 监听地址: http://0.0.0.0:8000
📚 API文档: http://0.0.0.0:8000/docs
📖 ReDoc文档: http://0.0.0.0:8000/redoc
⚙️  配置文件: .env

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
✓ 配置加载成功
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 访问 API 文档

打开浏览器访问 **http://localhost:8000/docs** 查看交互式 API 文档（Swagger UI）。

在文档页面你可以：
- 查看所有可用的 API 端点
- 直接在浏览器中测试 API
- 查看请求/响应示例

## 快速测试

### 1. 健康检查

```bash
curl http://localhost:8000/health
```

### 2. 获取代理

```bash
# 获取 5 个代理
curl "http://localhost:8000/api/v1/get-proxy?count=5"

# 获取 10 个美国的 HTTP 代理，最低分数 80
curl "http://localhost:8000/api/v1/get-proxy?count=10&protocol=http&country=US&min_score=80"
```

### 3. 爬取自定义 URL

```bash
curl -X POST "http://localhost:8000/api/v1/crawl-custom" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/proxy-list",
    "max_pages": 3,
    "use_ai": false,
    "no_store": true
  }'
```

### 4. 运行完整爬虫

```bash
curl -X POST "http://localhost:8000/api/v1/run" \
  -H "Content-Type: application/json" \
  -d '{"quick_test": true}'
```

### 5. 使用 Python 测试客户端

```bash
python tests/test_api_server.py
```

## 主要 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/v1/crawl-custom` | POST | 爬取自定义 URL |
| `/api/v1/run` | POST | 运行完整爬虫（后台） |
| `/api/v1/check` | POST | 检查代理（后台） |
| `/api/v1/get-proxy` | GET | 获取代理 |
| `/api/v1/diagnose/sources` | GET | 诊断代理源 |
| `/api/v1/diagnose/pipeline` | GET | 诊断数据管道 |

## 更多信息

查看完整文档：[API_SERVER.md](./API_SERVER.md)
