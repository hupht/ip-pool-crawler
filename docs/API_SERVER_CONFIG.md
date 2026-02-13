# API 服务器配置示例

## 方式 1：使用配置文件（推荐）

在 `.env` 文件中配置：

```bash
# API 服务器配置
API_HOST=0.0.0.0              # 监听所有网络接口
API_PORT=8000                 # 默认端口
```

然后直接启动：
```bash
python cli.py server
```

## 方式 2：命令行参数覆盖

即使配置了 `.env`，命令行参数也会优先生效：

```bash
# 使用不同的端口
python cli.py server --port 9000

# 仅本地访问
python cli.py server --host 127.0.0.1

# 同时指定主机和端口
python cli.py server --host 127.0.0.1 --port 8080
```

## 配置优先级

**优先级从高到低**：
1. 命令行参数 `--host` 和 `--port`
2. 环境变量 `API_HOST` 和 `API_PORT`（在 `.env` 中配置）
3. 默认值 `0.0.0.0:8000`

## 常用配置场景

### 开发环境（仅本地访问）
```bash
# .env
API_HOST=127.0.0.1
API_PORT=8000
```

### 生产环境（允许远程访问）
```bash
# .env
API_HOST=0.0.0.0
API_PORT=8000
```

### 使用反向代理（如 Nginx）
```bash
# .env
API_HOST=127.0.0.1            # 仅内部访问
API_PORT=8000
```

然后在 Nginx 中配置：
```nginx
server {
    listen 80;
    server_name api.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 验证配置

检查当前配置：
```bash
python -c "from crawler.config import Settings; s = Settings.from_env(); print(f'Host: {s.api_host}, Port: {s.api_port}')"
```

输出示例：
```
Host: 0.0.0.0, Port: 8000
```
