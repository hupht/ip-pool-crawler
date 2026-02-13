# 数据库自动初始化设计文档

## 概述

在首次爬取（或任何涉及 MySQL 操作时），如果遇到数据库或表不存在的错误（MySQL 错误代码 1146 或 1049），系统会自动创建数据库和表结构，无需手动执行 SQL schema。

## 需求

- **触发时机**：首次爬取时，如遇数据库/表不存在，自动创建
- **创建方式**：使用 `sql/schema.sql` 中的 DDL 语句
- **建库建表**：自动创建数据库（如不存在）并执行 schema
- **错误处理**：仅对 1146（表不存在）和 1049（数据库不存在）重试；其他错误正常抛出

## 架构设计

### 核心模块：`crawler/storage.py`

新增三个核心函数：

1. **`_load_schema() -> str`**
   - 从 `sql/schema.sql` 读取 DDL 内容
   - 返回原始 SQL 字符串

2. **`_init_database_and_schema(settings: Settings) -> None`**
   - 第一步：连接到 MySQL 服务器（不指定数据库）
   - 执行 `CREATE DATABASE IF NOT EXISTS <db_name> CHARACTER SET utf8mb4`
   - 第二步：连接到目标数据库
   - 解析并执行 schema.sql 中的所有 CREATE TABLE 语句
   - 异常时向上抛出，由调用者处理

3. **`_run_with_schema_retry(conn, settings, runner) -> T`**
   - 通用重试包装函数
   - 调用 `runner(cursor)` 执行实际 SQL 操作
   - 捕获 ProgrammingError，检查错误代码
   - 若为 1146 或 1049 且 settings 非空，调用初始化并重新建立连接
   - 第二次执行 runner
   - 返回 runner 的结果

### 集成点

所有 MySQL 读写函数包装为内部函数，通过 `_run_with_schema_retry` 执行：

- `upsert_source()`
- `upsert_proxy()`
- `update_proxy_check()`
- `fetch_check_batch()`
- `update_proxy_check_with_window()`
- `fetch_proxy_countries()`
- `fetch_mysql_candidates()`

### 全局 Settings 注册

为支持重试时访问配置，新增：

- **`_settings_for_retry: Optional[Settings]`** - 全局变量
- **`set_settings_for_retry(settings: Settings) -> None`** - 设置函数

在以下入口调用 `set_settings_for_retry(settings)`：

- `crawler/pipeline.py`: `run_once()` 开始处
- `tools/check_pool.py`: `run_check_batch()` 开始处
- `tools/get_proxy.py`: `run_from_args()` 开始处

## 数据流

```
用户执行: python cli.py run
    ↓
main()
    ↓
run_once(settings)
    ↓
set_settings_for_retry(settings)  ← 注册全局 settings
    ↓
get_mysql_connection()  → (连接到 MySQL)
    ↓
upsert_proxy(...)  ← 首条记录入库
    ↓
_run_with_schema_retry()
    ├─ runner(cursor) 执行 INSERT
    ├─ ❌ 捕获 ProgrammingError(1146, "Table doesn't exist")
    ├─ 调用 _init_database_and_schema(settings)
    │  ├─ 创建数据库
    │  └─ 执行 schema.sql
    ├─ conn.ping(reconnect=True)
    └─ 重新执行 runner(cursor) → ✅ 成功
    ↓
继续爬取流程
```

## 测试覆盖

### 单元测试（`tests/test_schema_auto_init.py`）

1. `test_load_schema_returns_sql_content` - schema 加载成功
2. `test_init_database_creates_database_and_tables` - 初始化创建表
3. `test_run_with_schema_retry_retries_on_table_not_found` - 1146 错误重试
4. `test_run_with_schema_retry_retries_on_database_not_found` - 1049 错误重试
5. `test_run_with_schema_retry_no_retry_on_other_errors` - 其他错误不重试
6. `test_run_with_schema_retry_no_retry_when_settings_none` - settings 为空不重试

### 现有测试

所有现有测试仍通过（27 项），包括：
- 存储层测试
- 流水线烟雾测试
- 校验器测试

## 使用场景

### 场景 1：首次运行爬虫

```bash
python cli.py run
```

输出：
```
(首次遇到 1146 或 1049 错误)
自动创建数据库 → 执行 schema.sql → 继续爬取
```

### 场景 2：数据库被意外删除

```bash
mysql> DROP DATABASE ip_pool;

$ python cli.py run
(遇到 1049 Unknown database)
自动创建 → 继续爬取
```

### 场景 3：特定表被删除

```bash
mysql> DROP TABLE ip_pool.proxy_ips;

$ python cli.py check
(遇到 1146 Table doesn't exist)
自动执行 schema.sql → 继续检查
```

## 边界情况处理

| 情况 | 行为 | 原因 |
|------|------|------|
| 数据库存在，表存在 | 正常操作，不进入 retry 路径 | 初始化逻辑只在错误时触发 |
| 数据库不存在 | 创建数据库 + 执行 schema | 1049 错误捕获 |
| 表不存在 | 执行 schema（database 已创建） | 1146 错误捕获 |
| 权限不足（1403） | 抛出异常，不重试 | 需要用户手动修复权限 |
| settings 为 None | 不重试，抛出异常 | 无配置无法初始化 |
| schema.sql 丢失 | 初始化时报 FileNotFoundError | 需要检查项目完整性 |

## 后续优化机会

1. **日志**：添加 DEBUG 日志记录初始化步骤
2. **超时**：大表初始化时可能耗时较长，可配置超时
3. **幂等性**：多个并发进程同时重试时的竞态条件处理
4. **恢复策略**：初始化失败时的回滚机制

## 兼容性

- 向后兼容：现有代码不需修改，自动获得初始化能力
- 不依赖新依赖：仅使用 pymysql 原生功能
- 支持所有现有命令：run / check / get-proxy 等均支持自动初始化
