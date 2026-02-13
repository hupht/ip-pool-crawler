# 审计级日志系统 - 实现步骤

## 概述

实现一个完整的**审计级日志系统**，日志存储在**数据库（保留30天）和文件**中，支持**配置化脱敏**。

---

## 实现步骤

### Step 1: 创建日志模块结构

```bash
mkdir -p ip-pool-crawler/crawler/logging
touch ip-pool-crawler/crawler/logging/__init__.py
touch ip-pool-crawler/crawler/logging/logger.py
touch ip-pool-crawler/crawler/logging/formatters.py
touch ip-pool-crawler/crawler/logging/handlers.py
touch ip-pool-crawler/crawler/logging/context.py
```

### Step 2: 扩展配置文件

**编辑 `crawler/config.py`，新增日志配置字段**

在 `Settings` dataclass 中新增：

```python
# 日志配置
log_level: str = "INFO"
log_file_path: str = "./logs/crawler.log"
log_file_max_size_mb: int = 100
log_file_backup_count: int = 10
log_db_mask_sensitive: bool = True      # 数据库日志脱敏
log_file_mask_sensitive: bool = False   # 文件日志不脱敏
log_db_retention_days: int = 30
log_archive_path: str = "./logs/archive"
```

在 `from_env()` 方法中新增对应的环境变量加载逻辑。

### Step 3: 扩展 schema.sql

**编辑 `sql/schema.sql`，在末尾添加日志表和事件**

添加：
- `audit_logs` 表（存储所有日志）
- `cleanup_audit_logs` 事件（自动删除 30 天前的日志）

### Step 4: 实现脱敏工具

**创建 `crawler/logging/formatters.py`**

实现：
- `SensitiveDataMasker` 类：脱敏密码、IP 等敏感信息
- `LogFormatter` 类：将日志记录格式化为可读的文本

### Step 5: 实现核心日志记录器

**创建 `crawler/logging/logger.py`**

实现：
- `AuditLogger` 类：支持 4 种日志方法
  - `log_db_operation()` - 数据库操作
  - `log_http_request()` - HTTP 请求
  - `log_tcp_check()` - TCP 检查
  - `log_pipeline_event()` - 流程事件
- `get_logger()` 全局函数：获取单例

### Step 6: 集成到现有代码

修改以下文件，在关键函数中调用日志：

- `crawler/storage.py` - 所有数据库操作函数
- `crawler/fetcher.py` - HTTP 请求函数
- `crawler/validator.py` - TCP 检查函数
- `crawler/pipeline.py` - 流程入口函数

### Step 7: 更新 `.env.example`

添加日志配置示例：
```dotenv
LOG_LEVEL=INFO
LOG_FILE_PATH=./logs/crawler.log
LOG_FILE_MAX_SIZE_MB=100
LOG_FILE_BACKUP_COUNT=10
LOG_DB_MASK_SENSITIVE=true
LOG_FILE_MASK_SENSITIVE=false
LOG_DB_RETENTION_DAYS=30
LOG_ARCHIVE_PATH=./logs/archive
```

### Step 8: 验证 requirements.txt

确保包含所有必要的依赖（无需新增）

### Step 9: 创建测试

**创建 `tests/test_audit_logging.py`**

测试：
- 脱敏功能（密码、IP）
- 日志记录（文件、数据库）
- 日志级别过滤
- 敏感信息处理

### Step 10: 文档更新

- 更新 [QUICK_START.md](../QUICK_START.md) - 添加日志查询示例
- 创建日志查询指南 - 如何从数据库和文件查询日志
- 更新 [DEPLOYMENT.md](../DEPLOYMENT.md) - 添加日志验证项

---

## 关键代码模板

### 在存储层集成

```python
from crawler.logging.logger import get_logger

def upsert_proxy(...) -> None:
    logger = get_logger()
    start_time = time.time()
    
    def runner(cursor):
        # 执行 SQL
        cursor.execute(...)
        
        # 记录日志
        logger.log_db_operation(
            operation="INSERT",
            table="proxy_ips",
            affected_rows=1,
            sql="INSERT INTO proxy_ips (...)",
            params={"ip": ip, "port": port},
            duration_ms=int((time.time() - start_time) * 1000),
            after_data={"ip": ip, "port": port},
        )
    
    _run_with_schema_retry(conn, _settings_for_retry, runner)
```

### 在请求层集成

```python
from crawler.logging.logger import get_logger

def fetch_source(source: Source, settings: Settings):
    logger = get_logger(settings)
    start_time = time.time()
    
    try:
        response = requests.get(...)
        logger.log_http_request(
            url=source.url,
            status_code=response.status_code,
            bytes_received=len(response.text),
            latency_ms=int((time.time() - start_time) * 1000),
        )
        return response.text, response.status_code
    except Exception as e:
        logger.log_http_request(
            url=source.url,
            status_code=0,
            error=e,
            level="ERROR",
        )
        return "", 0
```

---

## 检查清单

- [ ] Step 1: 创建日志模块结构
- [ ] Step 2: 扩展 config.py
- [ ] Step 3: 扩展 schema.sql
- [ ] Step 4: 实现 formatters.py
- [ ] Step 5: 实现 logger.py
- [ ] Step 6: 集成到 storage、fetcher、validator、pipeline
- [ ] Step 7: 更新 .env.example
- [ ] Step 8: 验证 requirements.txt
- [ ] Step 9: 创建测试文件
- [ ] Step 10: 运行测试并验证
- [ ] Step 11: 测试脱敏效果
- [ ] Step 12: 更新文档

---

## 验证方式

### 验证文件日志

```bash
tail -f logs/crawler.log
```

### 验证数据库日志

```sql
-- 查看最近的日志
SELECT operation_type, action, created_at 
FROM audit_logs 
ORDER BY created_at DESC 
LIMIT 10;

-- 查看错误日志
SELECT operation_type, action, error_message, created_at 
FROM audit_logs 
WHERE log_level = 'ERROR' 
ORDER BY created_at DESC;

-- 查看特定表的操作
SELECT sql_operation, table_name, affected_rows, duration_ms 
FROM audit_logs 
WHERE table_name = 'proxy_ips' 
ORDER BY created_at DESC 
LIMIT 20;
```

### 验证脱敏效果

```sql
-- 查看脱敏后的数据
SELECT sql_params, request_url 
FROM audit_logs 
WHERE log_level = 'ERROR' 
LIMIT 5;
```

---

现在可以开始实现了！建议按顺序执行 Step 1-10，最后进行文档更新（Step 12）。
