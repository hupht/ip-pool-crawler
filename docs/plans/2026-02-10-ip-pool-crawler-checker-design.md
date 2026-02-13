# IP Pool Checker Design

## 背景
需要新增独立脚本，对数据库中的代理 IP 做可用性检测。检测失败在 24h 窗口内累计 5 次后进行逻辑删除；检测成功则更新最后检查时间并清零失败计数。

## 目标
- 以批处理方式检测未删除代理，保证最终全覆盖。
- 失败按时间窗口累计，达到阈值后逻辑删除。
- 成功时更新检查时间并清零失败窗口。

## 非目标
- 不做物理删除。
- 不在该脚本中写入 Redis 池（保持解耦）。

## 数据模型
在 `proxy_ips` 表新增字段：
- `is_deleted` TINYINT(1) NOT NULL DEFAULT 0
- `fail_window_start` DATETIME NULL

规则：
- 失败：若 `fail_window_start` 为空或距当前时间超过 24h，则设置为当前时间且 `fail_count=1`；否则 `fail_count=fail_count+1`。
- 成功：`fail_count=0`，`fail_window_start=NULL`。
- 若失败后 `fail_count>=5` 且窗口仍在 24h 内，则 `is_deleted=1`。
- 重新抓取出现：`is_deleted=0`，并清空 `fail_window_start` 与 `fail_count`。

## 处理流程
1. 读取配置，建立 MySQL 连接。
2. 分页取数：`is_deleted=0`，按 `last_checked_at` 升序、`id` 升序取一批（默认 1000）。
3. 使用线程池并发检测；每条检测包含 3 次 TCP 重试，间隔 3 秒，任一次成功即判定成功。
4. 写回检测结果与窗口计数逻辑。
5. 退出（脚本每次运行处理一批）。

## 覆盖策略
- 分页排序以"最久未检查优先"，保证多次运行最终全覆盖。
- 游标使用 `(last_checked_at, id)`，避免重复或遗漏。

## 配置项
建议新增环境变量：
- `CHECK_BATCH_SIZE`（默认 1000）
- `CHECK_WORKERS`（默认 20）
- `CHECK_RETRIES`（默认 3）
- `CHECK_RETRY_DELAY`（默认 3 秒）
- `FAIL_WINDOW_HOURS`（默认 24）
- `FAIL_THRESHOLD`（默认 5）

## 错误处理
- 单条检测异常不影响整批，按失败处理并记录。
- 数据库更新按主键条件更新，确保幂等。

## 测试
- 单元测试：覆盖失败窗口逻辑与逻辑删除阈值。
- 集成测试：模拟批量分页与检测结果写回。

## 风险与缓解
- 批量过大导致检测耗时：控制 `CHECK_BATCH_SIZE` 与 `CHECK_WORKERS`。
- 失败窗口统计误差：通过 `fail_window_start` 记录窗口起点。
