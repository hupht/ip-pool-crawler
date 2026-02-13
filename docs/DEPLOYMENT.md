# 生产部署指南

完整的生产环境部署、配置和验证清单。

## 📋 部署前检查清单

### 前置环境要求

- [ ] Python 3.10+ 已安装
- [ ] MySQL 5.7+ 已安装且正在运行
- [ ] Redis 3.0+ 已安装且正在运行
- [ ] 服务器有 10GB+ 可用磁盘空间
- [ ] 服务器有 2GB+ 可用内存
- [ ] 网络能访问代理源（geonode.com 等）

### 验证环境

```bash
# Python 版本
python --version                 # 应 >= 3.10

# MySQL 连接
mysql -h 127.0.0.1 -u root -p -e "SELECT VERSION();"

# Redis 连接
redis-cli PING                   # 应返回 PONG

# 网络连通性
curl -I https://proxylist.geonode.com
```

---

## 🚀 部署步骤

### 步骤 1: 获取代码

```bash
# 克隆或下载项目
git clone https://github.com/your-repo/ip-pool-crawler.git
cd ip-pool-crawler

# 或解压压缩包
unzip ip-pool-crawler.zip
cd ip-pool-crawler
```

### 步骤 2: 安装依赖

```bash
# 常规安装
pip install -r requirements.txt

# 使用国内源加速（可选）
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple
```

**验证安装**：
```bash
python -c "import requests, pymysql, redis; print('✓ 依赖安装成功')"
```

### 步骤 3: 配置环境

创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入生产环境配置：

```dotenv
# ============ MySQL 配置 ============
MYSQL_HOST=192.168.1.100        # MySQL 服务器地址
MYSQL_PORT=3306
MYSQL_USER=crawler              # 建议用专用账户
MYSQL_PASSWORD=your_secure_password
MYSQL_DATABASE=ip_pool

# ============ Redis 配置 ============
REDIS_HOST=192.168.1.101        # Redis 服务器地址
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=                 # 如果启用了认证，填入密码

# ============ HTTP 配置 ============
HTTP_TIMEOUT=15
HTTP_RETRIES=2
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64)

# ============ 抓取配置 ============
SOURCE_WORKERS=3
VALIDATE_WORKERS=40

# ============ 检查配置 ============
CHECK_BATCH_SIZE=1000
CHECK_WORKERS=30
CHECK_RETRIES=3
CHECK_RETRY_DELAY=5
FAIL_WINDOW_HOURS=24
FAIL_THRESHOLD=5

# ============ 日志配置 ============
LOG_LEVEL=INFO
LOG_FILE_PATH=/var/log/ip-crawler/audit.log
LOG_DB_WRITE_ENABLED=true
LOG_DB_MASK_SENSITIVE=true
LOG_FILE_MASK_SENSITIVE=false
LOG_DB_RETENTION_DAYS=30

# ============ 动态爬虫配置 ============
DYNAMIC_CRAWLER_ENABLED=true
MAX_PAGES=10
MAX_PAGES_NO_NEW_IP=3
PAGE_FETCH_TIMEOUT_SECONDS=30

# ============ LLM/AI 配置（可选）============
# 是否启用 AI 辅助解析
USE_AI_FALLBACK=false

# LLM API 配置（如需使用 AI 功能）
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your-api-key-here
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=3

# AI 触发条件
AI_TRIGGER_ON_LOW_CONFIDENCE=true
AI_TRIGGER_ON_NO_TABLE=true
AI_TRIGGER_ON_FAILED_PARSE=true

# AI 缓存和成本控制
AI_CACHE_ENABLED=true
AI_CACHE_TTL_HOURS=24
AI_COST_LIMIT_USD=1.0
```

**⚠️ LLM 配置说明**：
- 如不使用 AI 功能，保持 `USE_AI_FALLBACK=false`
- 支持 OpenAI、Azure OpenAI、本地 Ollama 等兼容 OpenAI API 的服务
- `AI_COST_LIMIT_USD` 为单次会话成本上限，防止意外费用
- 详见：[LLM 集成指南](./LLM_INTEGRATION.md)

⚠️ **安全建议**：
- 使用强密码
- 为程序创建专冶 MySQL 账户
- 使用绝对路径指定日志目录
- 限制 `.env` 文件权限：`chmod 600 .env`

### 步骤 4: 验证连接

```bash
# 测试 MySQL
mysql -h 192.168.1.100 -u crawler -p -e "SELECT VERSION();"

# 测试 Redis
redis-cli -h 192.168.1.101 PING

# 测试 Python 连接
python -c "
from crawler.config import Settings
from crawler.storage import get_mysql_connection, get_redis_client

settings = Settings.from_env()
mysql_conn = get_mysql_connection(settings)
print('✓ MySQL 连接成功')

redis_client = get_redis_client(settings)
print('✓ Redis 连接成功')
"
```

### 步骤 5: 初始化数据库

程序会自动初始化数据库和表，首次运行时：

```bash
python cli.py run
```

**验证初始化**：
```sql
mysql> SHOW TABLES FROM ip_pool;
-- 应返回：proxy_sources, proxy_ips, audit_logs 等表
```

### 步骤 5.5: 部署后验证（轻量）

部署完成后，建议运行轻量验证脚本。该脚本只对每个源抓取 1 条样本并输出验证报告：

```bash
python cli.py verify-deploy
```

输出报告：`reports/verify_report.md`（中英文双语）

**文档健康检查（建议）**：
```bash
python cli.py check-docs-links
```

用途：
- 本地发布前检查文档链接
- CI 中复用（坏链返回非 0 退出码，可阻断合并）

**常见未抓取成功原因**：
- 网络不可达 / DNS 解析失败
- 目标站点限制访问（403/429）
- 超时或 TLS 握手失败
- 站点临时故障或返回空数据

### 步骤 6: 设置定时任务

#### Linux/Mac (Crontab)

```bash
# 编辑 crontab
crontab -e
```

添加以下任务：

```cron
# 每天凌晨 3 点运行爬虫
0 3 * * * cd /path/to/ip-pool-crawler && python cli.py run >> /var/log/ip-crawler/cron.log 2>&1

# 每 30 分钟运行一次检查
*/30 * * * * cd /path/to/ip-pool-crawler && python cli.py check >> /var/log/ip-crawler/cron.log 2>&1
```

**验证任务**：
```bash
crontab -l
```

#### Windows (任务计划)

1. 打开"任务计划程序"（`Win+R` → `taskschd.msc`）
2. 右键"任务计划库" → "创建基本任务"
3. 配置：
   - **名称**：IP Pool Crawler - Run
   - **触发器**：每天 3:00 AM
   - **操作**：
     - 程序：`C:\Python310\python.exe`
     - 参数：`cli.py run`
     - 工作目录：`C:\path\to\ip-pool-crawler`

4. 创建第二个任务（检查）：
   - **名称**：IP Pool Crawler - Check
   - **触发器**：每 30 分钟
   - 其他配置相同

### 步骤 7: 日志和监控目录

```bash
# 创建日志目录
mkdir -p /var/log/ip-crawler

# 设置权限
chmod 755 /var/log/ip-crawler

# 创建日志轮转配置（Linux）
sudo tee /etc/logrotate.d/ip-crawler > /dev/null << EOF
/var/log/ip-crawler/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    create 0640 $(whoami) $(whoami)
}
EOF
```

---

## ✅ 部署后验证

### 功能验证

```bash
# 1. 测试爬虫
python cli.py run

# 预期：成功获取代理，写入 MySQL 和 Redis

# 2. 检查数据
mysql -u crawler -p ip_pool -e "SELECT COUNT(*) as proxy_count FROM proxy_ips;"
redis-cli ZCARD proxy:alive

# 3. 获取代理
python cli.py get-proxy --protocol http --count 3

# 4. Cron 日志检查
tail -20 /var/log/ip-crawler/cron.log
```

### 性能基准

**预期时间**：
- 首次爬虫：1-3 分钟（包括建表）
- 后续爬虫：2-5 分钟
- 检查任务：3-10 分钟
- 获取代理：< 1 秒

**预期数据**：
- 总代理数：500-1500
- 可用代理：50-200（3-15%）
- 数据库大小：10-50MB
- Redis 内存：5-20MB

### 监控指标

```sql
-- 检查代理统计
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN is_alive=1 THEN 1 ELSE 0 END) as alive,
    SUM(CASE WHEN is_deleted=1 THEN 1 ELSE 0 END) as deleted
FROM proxy_ips;

-- 检查最后更新时间
SELECT MAX(updated_at) as last_update FROM proxy_ips;

-- 检查日志统计
SELECT 
    DATE(created_at) as date,
    COUNT(*) as logs,
    SUM(CASE WHEN log_level='ERROR' THEN 1 ELSE 0 END) as errors
FROM audit_logs
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 7;
```

---

## 🔒 安全加固

### 1. MySQL 安全

```sql
-- 为程序创建专用账户
CREATE USER 'crawler'@'127.0.0.1' IDENTIFIED BY 'strong_password';

-- 授予最少权限
GRANT SELECT, INSERT, UPDATE, DELETE ON ip_pool.* TO 'crawler'@'127.0.0.1';
GRANT EVENT ON ip_pool.* TO 'crawler'@'127.0.0.1';  -- 用于日志清理事件

-- 刷新权限
FLUSH PRIVILEGES;

-- 禁用远程 root 登录
DELETE FROM mysql.user WHERE User='root' AND Host!='localhost';
```

### 2. Redis 安全

```bash
# 编辑 redis.conf
# requirepass your_strong_password
# bind 127.0.0.1
# protected-mode yes

# 重启 Redis
redis-cli SHUTDOWN
redis-server /etc/redis/redis.conf
```

### 3. 文件权限

```bash
# 限制 .env 权限
chmod 600 .env

# 日志文件权限
chmod 644 /var/log/ip-crawler/audit.log

# 代码目录权限
chmod 755 /path/to/ip-pool-crawler
chmod 644 /path/to/ip-pool-crawler/*.py
```

### 4. 防火墙

```bash
# Linux (UFW)
sudo ufw allow 3306/tcp from 127.0.0.1  # MySQL
sudo ufw allow 6379/tcp from 127.0.0.1  # Redis
sudo ufw allow 80/tcp                   # HTTP（如果开放 API）
sudo ufw allow 443/tcp                  # HTTPS
```

---

## 📊 监控和告警

### 1. 操作监控

```bash
# 实时监控日志
tail -f /var/log/ip-crawler/audit.log

# 搜索错误
grep ERROR /var/log/ip-crawler/audit.log

# 统计每日操作
grep "^202" /var/log/ip-crawler/audit.log | cut -d' ' -f1 | sort | uniq -c
```

### 2. 数据库监控

```sql
-- 监控代理池健康状态
SELECT 
    CEIL(COUNT(*) / 1000) * 1000 as total_proxies,
    SUM(CASE WHEN is_alive=1 THEN 1 ELSE 0 END) as alive_proxies,
    ROUND(100 * SUM(CASE WHEN is_alive=1 THEN 1 ELSE 0 END) / COUNT(*), 2) as availability_rate
FROM proxy_ips;

-- 监控近期性能
SELECT 
    AVG(duration_ms) as avg_duration_ms,
    MAX(duration_ms) as max_duration_ms,
    COUNT(*) as operations
FROM audit_logs
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR);

-- 监控错误率
SELECT 
    COUNT(*) as total_ops,
    SUM(CASE WHEN log_level='ERROR' THEN 1 ELSE 0 END) as error_count,
    ROUND(100 * SUM(CASE WHEN log_level='ERROR' THEN 1 ELSE 0 END) / COUNT(*), 2) as error_rate_pct
FROM audit_logs
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR);
```

### 3. 告警规则

**建议设置的告警**：

| 指标 | 阈值 | 严重程度 |
|------|------|--------|
| 错误率 | > 5% | 🟠 中等 |
| 平均延迟 | > 1000ms | 🟠 中等 |
| 可用代理数 | < 50 | 🟡 轻微 |
| 数据库日志大小 | > 1GB | 🟡 轻微 |
| Cron 任务失败 | 任何失败 | 🔴 高 |

---

## 📈 性能优化

### 1. MySQL 优化

```sql
-- 添加索引
ALTER TABLE proxy_ips ADD INDEX idx_is_alive_created (is_alive, first_seen_at);
ALTER TABLE proxy_ips ADD INDEX idx_country_protocol (country, protocol);

-- 查询计划分析
EXPLAIN SELECT * FROM proxy_ips WHERE country='US' AND protocol='http' LIMIT 10;

-- 表优化
OPTIMIZE TABLE proxy_ips;
OPTIMIZE TABLE proxy_sources;
OPTIMIZE TABLE audit_logs;
```

### 2. Redis 优化

```bash
# 获取 Redis 统计
redis-cli INFO stats

# 监控内存
redis-cli INFO memory

# 设置内存上限
redis-cli CONFIG SET maxmemory 512mb

# 设置过期策略
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### 3. 应用优化

```dotenv
# 增加并发（如果服务器足够强大）
SOURCE_WORKERS=5
VALIDATE_WORKERS=60

# 或降低并发（如果资源紧张）
SOURCE_WORKERS=1
VALIDATE_WORKERS=20

# 增加 HTTP 连接池大小
HTTP_TIMEOUT=20
HTTP_RETRIES=2
```

---

## 🔄 升级和维护

### 定期维护任务

```bash
# 每周
# - 查看性能日志
# - 检查错误率
# - 备份数据库

# 每月
# - 清理过期日志
# - 优化表索引
# - 备份完整数据库

# 每季度
# - 检查代理源是否失效
# - 更新依赖
# - 性能基准测试
```

### 数据备份

```bash
# MySQL 备份
mysqldump -u crawler -p ip_pool > /backup/ip_pool_$(date +%Y%m%d).sql

# Redis 备份
redis-cli --rdb /backup/redis_$(date +%Y%m%d).rdb

# 代码备份
tar -czf /backup/ip-pool-crawler_$(date +%Y%m%d).tar.gz /path/to/ip-pool-crawler
```

### 灾难恢复

```bash
# 恢复 MySQL
mysql -u crawler -p ip_pool < /backup/ip_pool_20260212.sql

# 恢复 Redis
redis-cli SHUTDOWN
cp /backup/redis_20260212.rdb /var/lib/redis/dump.rdb
redis-server
```

---

## 🚨 故障处理

### 常见故障响应

| 故障 | 影响 | 恢复时间 | 处理方式 |
|------|------|--------|--------|
| MySQL 宕机 | 无法入库 | 1-5 分钟 | 重启 MySQL，检查磁盘 |
| Redis 宕机 | 无法获取代理 | 1-2 分钟 | 重启 Redis，清理内存 |
| 网络中断 | 无法抓取 | 取决于网络 | 等待网络恢复 |
| 代理源失效 | 无新代理 | 需要更新源 | 更换数据源或等待源修复 |
| 磁盘满 | 无法写入日志 | 30+ 分钟 | 清理旧日志/扩容 |

---

## 📞 支持和反馈

- 📖 查看 [故障排查指南](./TROUBLESHOOTING.md)
- 🔍 查看 [审计日志](./AUDIT_LOGGING.md)
- 💻 查看 [架构设计](./ARCHITECTURE.md)

---

**相关文档**：
- 👉 [快速开始](./QUICK_START.md)
- 👉 [命令行参考](./CLI_REFERENCE.md)
- 👉 [审计日志](./AUDIT_LOGGING.md)
