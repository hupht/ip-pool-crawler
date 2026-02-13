# 审计日志系统

完整的审计日志系统说明，包括工作原理、查询方法、监控告警等。

## 📋 概览

IP Pool Crawler 包含一个完整的审计日志系统，用于：
- 📍 **追踪所有操作** - 数据库操作、HTTP 请求、TCP 检查、流程事件
- 🔐 **敏感数据保护** - IP 地址、密码等自动脱敏
- 📊 **性能分析** - 记录执行时间、失败原因、性能指标
- 🔍 **故障排查** - 完整的操作历史便于诊断问题
- 📈 **监控告警** - 支持设置告警规则

> 2026-02-13 更新：`crawl-custom` 动态爬虫链路已接入审计日志，开始/完成/失败及页面抓取请求会写入 `audit_logs`。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────┐
│              应用代码                                 │
├─────────────────────────────────────────────────────┤
│  storage.py  │ fetcher.py │ validator.py │ pipeline.py
├─────────────────────────────────────────────────────┤
│              get_logger()                            │
│              ↓ ↓ ↓ ↓ ↓ ↓ ↓ ↓ ↓ ↓                    │
│         AuditLogger                                  │
│         ├─→ SensitiveDataMasker                      │
│         ├─→ LogFormatter                             │
│         └─→ 双写引擎                                 │
├─────────────────────────────────────────────────────┤
│  MySQL (audit_logs 表)  │  文件 (./logs/audit.log) │
└─────────────────────────────────────────────────────┘
```

## 🔧 配置

### 环境变量 (.env)

```dotenv
# 日志级别
LOG_LEVEL=INFO              # DEBUG/INFO/WARNING/ERROR

# 文件日志
LOG_FILE_PATH=./logs/audit.log

# 数据库日志
LOG_DB_WRITE_ENABLED=true   # 是否启用数据库日志
LOG_DB_RETENTION_DAYS=30    # 日志保留天数

# 脱敏设置
LOG_DB_MASK_SENSITIVE=true        # 数据库日志脱敏
LOG_FILE_MASK_SENSITIVE=false     # 文件日志脱敏

# 性能配置
LOG_DB_BATCH_SIZE=100       # 批量写入大小
```

### 配置说明

**LOG_LEVEL** - 日志级别过滤
- `DEBUG` - 记录所有信息（包含详细调试）
- `INFO` - 记录正常操作（默认）
- `WARNING` - 仅记录警告和错误
- `ERROR` - 仅记录错误

**LOG_DB_MASK_SENSITIVE** - 数据库中的脱敏
- `true` - IP、密码等敏感信息被脱敏存储
- `false` - 存储原始信息（不推荐）

**LOG_FILE_MASK_SENSITIVE** - 文件中的脱敏
- `true` - 文件日志中脱敏敏感信息
- `false` - 文件日志中记录原始信息

🔐 **建议**：
- 生产环境：DB + File 都启用脱敏
- 开发环境：File 不脱敏便于调试，DB 脱敏保护隐私

## 📝 记录的操作

### 动态爬虫（crawl-custom）

`crawl-custom` 当前会记录以下审计事件：

- `PIPELINE_START`：任务启动
- `HTTP_REQUEST`：页面抓取（含成功/失败状态）
- `PIPELINE_COMPLETE`：任务完成
- `PIPELINE_ERROR`：任务异常结束

同时，针对抓取第一页即失败的场景，也会在 `crawl_page_log` 写入失败页记录（`parse_success=0` + `error_message`），便于排障追踪。

### 1. 数据库操作 (DB_OPERATION)

记录所有 MySQL 操作。

**字段**：
```python
{
    "operation_type": "DB_OPERATION",
    "module_name": "storage",
    "action": "INSERT on proxy_ips",
    "sql_operation": "INSERT",        # INSERT/UPDATE/DELETE
    "table_name": "proxy_ips",
    "affected_rows": 50,              # 影响的行数
    "sql_statement": "INSERT INTO ...",
    "sql_params": {"ip": "192.168.1.***", ...},
    "before_data": {...},             # 更新前数据
    "after_data": {...},              # 更新后数据
    "duration_ms": 245,               # 执行耗时
    "log_level": "INFO"
}
```

**例子**：
- INSERT 100 条代理：`INSERT on proxy_ips (100 rows, 245ms)`
- UPDATE 代理可用性：`UPDATE on proxy_ips (1 rows, 15ms)`
- DELETE 过期日志：`DELETE on audit_logs (1000 rows, 2340ms)`

### 2. HTTP 请求 (HTTP_REQUEST)

记录所有 HTTP 抓取操作。

**字段**：
```python
{
    "operation_type": "HTTP_REQUEST",
    "module_name": "fetcher",
    "action": "Fetch from https://proxylist.geonode.com",
    "request_url": "https://proxylist.geonode.com/api/proxy-list?...",
    "request_status_code": 200,
    "bytes_received": 45678,
    "request_latency_ms": 523,
    "log_level": "INFO"
}
```

**例子**：
- 成功抓取：`HTTP 200 (45.6 KB, 523ms)`
- 重定向：`HTTP 301 (→ 45.6 KB, 312ms)`
- 失败：`HTTP 403 Forbidden (523ms)` ❌

### 3. TCP 检查 (TCP_CHECK)

记录每个代理的验证结果。

**字段**：
```python
{
    "operation_type": "TCP_CHECK",
    "module_name": "validator",
    "action": "TCP check 192.168.1.*** :8080 - OK",
    "request_status_code": 1,         # 1=成功, 0=失败
    "request_latency_ms": 120,
    "log_level": "DEBUG"              # TCP 检查通常是 DEBUG
}
```

**例子**：
- 成功：`TCP check 192.168.1.*** :8080 - OK (120ms)` ✅
- 失败：`TCP check 192.168.1.*** :8080 - FAIL (timeout)` ❌

### 4. 流程事件 (PIPELINE_*)

记录高级的流程事件。

**字段**：
```python
{
    "operation_type": "PIPELINE_COMPLETE",
    "module_name": "pipeline",
    "action": "Pipeline COMPLETE: run_once (648 items) [125000ms]",
    "data_count": 648,
    "duration_ms": 125000,
    "log_level": "INFO"
}
```

**事件类型**：
- `PIPELINE_START` - 流程开始
- `PIPELINE_COMPLETE` - 流程完成
- `PIPELINE_ERROR` - 流程出错

---

## 🔐 敏感数据脱敏

### 脱敏规则

自动识别并脱敏以下类型的敏感信息：

| 类型 | 脱敏前 | 脱敏后 | 规则 |
|------|--------|--------|------|
| **IP 地址** | 192.168.1.100 | 192.168.1.*** | 替换最后分段 |
| **密码** | secret123 | *** | 字段名包含 password |
| **API Key** | sk_live_abc123 | *** | 字段名包含 key、token |
| **Token** | token_xyz_123 | *** | 字段名包含 token |
| **授权** | Bearer xyz | *** | 字段名包含 auth |

### 脱敏示例

```python
# 原始数据
{
    "ip": "192.168.1.100",
    "password": "secret",
    "api_key": "sk_123",
    "port": 8080
}

# 脱敏后（启用脱敏时）
{
    "ip": "192.168.1.***",
    "password": "***",
    "api_key": "***",
    "port": 8080
}
```

### 存储对比

| 模式 | 数据库 | 文件 | 用途 |
|------|--------|------|------|
| 生产环境 | 脱敏 | 脱敏 | 最大隐私保护 |
| 测试环境 | 脱敏 | 不脱敏 | 诊断方便 |
| 开发环境 | 不脱敏 | 不脱敏 | 完全可见 |

---

## 📊 查询日志

### 数据库查询

所有查询都针对 `audit_logs` 表。

#### 1. 最近的操作（最常用）

```sql
SELECT created_at, log_level, operation_type, module_name, action, duration_ms
FROM audit_logs
ORDER BY log_id DESC
LIMIT 50;
```

#### 2. 查看特定模块的操作

```sql
-- 所有存储操作
SELECT created_at, sql_operation, table_name, affected_rows, duration_ms
FROM audit_logs
WHERE module_name = 'storage'
ORDER BY created_at DESC
LIMIT 50;

-- 所有 HTTP 请求
SELECT created_at, action, request_status_code, request_latency_ms
FROM audit_logs
WHERE module_name = 'fetcher'
ORDER BY created_at DESC
LIMIT 50;

-- 所有 TCP 检查
SELECT created_at, action, request_latency_ms
FROM audit_logs
WHERE module_name = 'validator'
ORDER BY created_at DESC
LIMIT 50;
```

#### 3. 查看错误日志

```sql
-- 所有错误
SELECT created_at, module_name, action, error_code, error_message
FROM audit_logs
WHERE log_level = 'ERROR'
ORDER BY created_at DESC
LIMIT 30;

-- 特定模块的错误
SELECT created_at, action, error_code, error_message, error_stack
FROM audit_logs
WHERE log_level = 'ERROR' AND module_name = 'storage'
ORDER BY created_at DESC;
```

#### 4. 性能分析

```sql
-- 耗时最长的 5 个数据库操作
SELECT created_at, sql_operation, table_name, affected_rows, duration_ms
FROM audit_logs
WHERE operation_type = 'DB_OPERATION'
ORDER BY duration_ms DESC
LIMIT 5;

-- 平均响应时间（最近 24 小时）
SELECT 
    DATE_FORMAT(created_at, '%H:00') as hour,
    COUNT(*) as count,
    AVG(duration_ms) as avg_duration_ms,
    MAX(duration_ms) as max_duration_ms
FROM audit_logs
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY DATE_FORMAT(created_at, '%H:00')
ORDER BY hour DESC;

-- 每个表的性能统计
SELECT 
    table_name,
    COUNT(*) as operations,
    AVG(duration_ms) as avg_duration_ms,
    MAX(duration_ms) as max_duration_ms,
    SUM(affected_rows) as total_rows
FROM audit_logs
WHERE operation_type = 'DB_OPERATION'
  AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY table_name
ORDER BY avg_duration_ms DESC;
```

#### 5. 可用性监控

```sql
-- 每小时的错误率
SELECT 
    DATE_FORMAT(created_at, '%Y-%m-%d %H:00') as hour,
    COUNT(*) as total_ops,
    SUM(CASE WHEN log_level = 'ERROR' THEN 1 ELSE 0 END) as errors,
    ROUND(100.0 * SUM(CASE WHEN log_level = 'ERROR' THEN 1 ELSE 0 END) / COUNT(*), 2) as error_rate_pct
FROM audit_logs
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY DATE_FORMAT(created_at, '%Y-%m-%d %H:00')
ORDER BY hour DESC;

-- 模块健康状态
SELECT 
    module_name,
    COUNT(*) as total_ops,
    SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN error_code IS NOT NULL THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
FROM audit_logs
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
GROUP BY module_name;
```

### 文件日志查询

日志文件位置：`./logs/audit.log`

```bash
# 查看最近的日志
tail -20 ./logs/audit.log

# 实时监控日志
tail -f ./logs/audit.log

# 搜索特定模块
grep "\[storage\]" ./logs/audit.log

# 搜索错误
grep "ERROR\|FAIL" ./logs/audit.log

# 统计操作数
grep -o "DB_OPERATION\|HTTP_REQUEST\|TCP_CHECK" ./logs/audit.log | sort | uniq -c
```

---

## 📈 监控告警

### 1. 错误率监控

创建告警：错误率 > 5% 时触发。

```sql
-- 每分钟检查
SELECT 
    DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i') as time,
    COUNT(*) as ops_count,
    SUM(CASE WHEN log_level = 'ERROR' THEN 1 ELSE 0 END) as error_count,
    ROUND(100.0 * SUM(CASE WHEN log_level = 'ERROR' THEN 1 ELSE 0 END) / COUNT(*), 2) as error_rate_pct
FROM audit_logs
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 MINUTE)
HAVING error_rate_pct > 5;
```

### 2. 性能监控

创建告警：操作平均耗时 > 1 秒时触发。

```sql
SELECT 
    DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i') as time,
    module_name,
    AVG(duration_ms) as avg_duration_ms
FROM audit_logs
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
GROUP BY module_name
HAVING AVG(duration_ms) > 1000;
```

### 3. 数据源可用性

创建告警：HTTP 失败次数 > 3 时触发。

```sql
SELECT 
    DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i') as time,
    action,
    COUNT(*) as attempt_count,
    SUM(CASE WHEN request_status_code != 200 THEN 1 ELSE 0 END) as failure_count
FROM audit_logs
WHERE operation_type = 'HTTP_REQUEST'
  AND created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
GROUP BY action
HAVING failure_count > 3;
```

---

## 🗂️ 日志轮转和清理

### 自动清理

数据库审计日志通过 MySQL 事件自动清理：

```sql
-- 创建的事件（已包含在 schema.sql 中）
CREATE EVENT cleanup_audit_logs
ON SCHEDULE EVERY 1 DAY
STARTS DATE_FORMAT(NOW(), '%Y-%m-%d 02:00:00')
DO 
  DELETE FROM audit_logs 
  WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
```

### 手动清理

```sql
-- 删除超过 30 天的日志
DELETE FROM audit_logs 
WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);

-- 删除特定模块的日志
DELETE FROM audit_logs
WHERE module_name = 'validator'
  AND created_at < DATE_SUB(NOW(), INTERVAL 7 DAY);

-- 删除特定错误的日志
DELETE FROM audit_logs
WHERE error_code = 'TimeoutError'
  AND created_at < DATE_SUB(NOW(), INTERVAL 3 DAY);
```

### 文件日志轮转

推荐使用 `logrotate`（Linux）：

```bash
# /etc/logrotate.d/ip-crawler
/path/to/ip-pool-crawler/logs/audit.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    create 0640 ubuntu ubuntu
}
```

---

## 🔍 常见查询场景

### 场景 1: 爬虫运行统计

```sql
-- 查看最后 10 次爬虫运行的统计
SELECT 
    created_at,
    action,
    duration_ms / 1000 as duration_sec,
    REGEXP_SUBSTR(action, '[0-9]+') as item_count
FROM audit_logs
WHERE operation_type LIKE 'PIPELINE_%'
ORDER BY created_at DESC
LIMIT 10;
```

### 场景 2: 数据源质量

```sql
-- 每个数据源的平均响应时间和成功率
SELECT 
    action,
    COUNT(*) as requests,
    AVG(request_latency_ms) as avg_latency_ms,
    SUM(CASE WHEN request_status_code = 200 THEN 1 ELSE 0 END) as success_count,
    ROUND(100.0 * SUM(CASE WHEN request_status_code = 200 THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
FROM audit_logs
WHERE operation_type = 'HTTP_REQUEST'
  AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY action
ORDER BY success_rate_pct DESC;
```

### 场景 3: 故障诊断

```sql
-- 最近的 20 个错误及其原因
SELECT 
    created_at,
    module_name,
    error_code,
    error_message,
    action
FROM audit_logs
WHERE log_level = 'ERROR'
ORDER BY created_at DESC
LIMIT 20;

-- 查看完整的错误堆栈
SELECT 
    created_at,
    module_name,
    error_code,
    error_stack
FROM audit_logs
WHERE log_level = 'ERROR'
  AND error_stack IS NOT NULL
ORDER BY created_at DESC
LIMIT 5;
```

### 场景 4: 资源使用

```sql
-- 数据库表大小和行数增长
SELECT 
    DATE(created_at) as date,
    table_name,
    COUNT(*) as operations,
    SUM(affected_rows) as total_rows_affected
FROM audit_logs
WHERE operation_type = 'DB_OPERATION'
  AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(created_at), table_name
ORDER BY date DESC, table_name;
```

---

## 💡 最佳实践

1. **定期检查日志**
   - 每日查看错误日志
   - 每周分析性能趋势
   - 每月生成统计报告

2. **设置告警**
   - 错误率 > 5%
   - 操作耗时 > 1 秒
   - HTTP 连续失败 > 3 次

3. **隐私保护**
   - 生产环境启用脱敏
   - 定期清理过期日志
   - 限制日志访问权限

4. **性能优化**
   - 定期清理过期日志
   - 为常用查询添加索引
   - 预留足够的磁盘空间

---

**相关文档**：
- 👉 [快速开始](./QUICK_START.md)
- 👉 [架构设计](./ARCHITECTURE.md)
- 👉 [故障排查](./TROUBLESHOOTING.md)
