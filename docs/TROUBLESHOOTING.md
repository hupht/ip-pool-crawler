# 故障排查指南

常见问题和解决方案。

## 🚀 启动问题

### 问题：`ModuleNotFoundError: No module named 'requests'`

**原因**：依赖未安装

**解决方案**：
```bash
pip install -r requirements.txt
```

**验证**：
```bash
python -c "import requests; print(requests.__version__)"
```

---

### 问题：`FileNotFoundError: [Errno 2] No such file or directory: '.env'`

**原因**：缺少 `.env` 配置文件

**解决方案**：
```bash
cp .env.example .env
# 然后编辑 .env 填入数据库信息
```

**验证**：
```bash
cat .env | grep MYSQL_HOST
```

---

## 🗄️ 数据库问题

### 问题：`pymysql.err.OperationalError: (1049, "Unknown database 'ip_pool'")`

**原因**：数据库不存在

**解决方案**（自动）：
- 首次运行时程序会自动创建数据库和表
- 只需确保 MySQL 连接配置正确

**手动解决**：
```bash
mysql -h 127.0.0.1 -u root -p
mysql> CREATE DATABASE ip_pool CHARACTER SET utf8mb4;
mysql> USE ip_pool;
mysql> SOURCE sql/schema.sql;
```

---

### 问题：`pymysql.err.OperationalError: (1045, "Access denied for user 'root'@'127.0.0.1'"`

**原因**：MySQL 用户名或密码错误

**解决方案**：
1. 验证 MySQL 连接
   ```bash
   mysql -h 127.0.0.1 -u root -p  # 输入正确的密码
   ```

2. 检查 `.env` 文件中的配置
   ```bash
   grep MYSQL_ .env
   ```

3. 确保配置与 MySQL 实际设置一致

**验证**：
```bash
python -c "from crawler.config import Settings; s = Settings.from_env(); print(f'Host: {s.mysql_host}, User: {s.mysql_user}')"
```

---

### 问题：`pymysql.err.ProgrammingError: (1146, "Table 'ip_pool.proxy_ips' doesn't exist")`

**原因**：表结构不存在或损坏

**解决方案**（自动）：
- 程序会自动检测并重新创建表

**手动重建**：
```bash
mysql -u root -p ip_pool < sql/schema.sql
```

**验证**：
```bash
mysql -u root -p ip_pool -e "SHOW TABLES;"
```

---

## 🔴 Redis 问题

### 问题：`redis.exceptions.ConnectionError: Error -3 Name or service not known`

**原因**：Redis 服务未启动或主机名错误

**解决方案**：
1. 检查 Redis 是否运行
   ```bash
   redis-cli ping  # 应返回 PONG
   ```

2. 如果 Redis 未启动，启动它
   ```bash
   # Linux/Mac
   redis-server
   
   # 或通过服务管理
   sudo systemctl start redis-server
   ```

3. 检查 `.env` 配置
   ```bash
   grep REDIS_ .env
   ```

**验证**：
```bash
redis-cli PING
redis-cli INFO server  # 查看 Redis 版本和内存
```

---

### 问题：`redis.exceptions.AuthenticationError: Client sent AUTH, but no password is set`

**原因**：`.env` 中配置了 Redis 密码，但 Redis 实际无密码

**解决方案**：
1. 编辑 `.env`，将 `REDIS_PASSWORD` 改为空
   ```dotenv
   REDIS_PASSWORD=
   ```

2. 或者为 Redis 设置密码
   ```bash
   redis-cli CONFIG SET requirepass your_password
   ```

**验证**：
```bash
# 测试无密码连接
redis-cli PING

# 或测试有密码连接
redis-cli -a your_password PING
```

---

### 问题：代理池为空，`get-proxy` 返回无结果

**原因**：
1. 爬虫未运行，没有获取代理
2. 代理全部被标记为不可用
3. 过滤条件太严格

**解决方案**：

**第一步**：检查 MySQL 中是否有代理
```bash
mysql -u root -p ip_pool -e "SELECT COUNT(*) FROM proxy_ips;"
```

**第二步**：检查 Redis 中是否有代理
```bash
redis-cli ZCARD proxy:alive
```

**第三步**：如果 MySQL 有但 Redis 没有，运行爬虫
```bash
python cli.py run
```

**第四步**：检查过滤条件
```bash
# 获取所有代理
python cli.py get-proxy --count 10

# 获取特定协议
python cli.py get-proxy --protocol http --count 5
```

---

## 🌐 网络问题

### 问题：`verify_deploy.py` 中数据源抓取失败（`fetch_failed`）

**现象**：报告中 `sources_passed` 偏低，部分源显示 `fetch_failed`。

**常见原因**：
- 网络不可达 / DNS 解析失败
- 站点限制访问（403/429）
- 超时或 TLS 握手失败
- 站点临时故障或返回空数据

**解决方案**：
1. 先运行诊断命令：
   ```bash
   python cli.py diagnose-sources
   ```
2. 检查本机网络和 DNS：
   ```bash
   ping proxylist.geonode.com
   nslookup proxylist.geonode.com
   ```
3. 适当提高超时：
   ```dotenv
   HTTP_TIMEOUT=15
   HTTP_RETRIES=2
   ```
4. 如果是 403/429，尝试更换网络或稍后再试。

### 问题：`requests.exceptions.ConnectionError: Connection refused`

**原因**：
1. 代理源无法访问
2. 网络连接问题
3. 源站被墙或宕机

**解决方案**：
1. 诊断数据源
   ```bash
   python cli.py diagnose-sources
   ```

2. 手动测试源站
   ```bash
   curl https://proxylist.geonode.com/api/proxy-list?limit=1
   ```

3. 检查网络连接
   ```bash
   ping 8.8.8.8
   ping proxylist.geonode.com
   ```

4. 检查防火墙
   ```bash
   # Linux
   sudo iptables -L -n | grep 443
   ```

---

### 问题：`requests.exceptions.Timeout: HTTPConnectionPool(host='...')`

**原因**：请求超时

**解决方案**：
1. 增加超时时间（`.env`）
   ```dotenv
   HTTP_TIMEOUT=20  # 增加到 20 秒
   ```

2. 检查网络速度
   ```bash
   speedtest
   ```

3. 尝试使用代理
   ```bash
   curl -x http://proxy:port https://example.com
   ```

---

## 📊 抓取问题

### 问题：抓取的代理数量为 0

**原因**：
1. 解析器错误
2. 源站格式改变
3. 网络问题

**解决方案**：
1. 诊断完整流程
   ```bash
   python cli.py diagnose-pipeline
   ```

2. 检查 HTML 解析
   ```bash
   python cli.py diagnose-html
   ```

3. 查看日志
   ```bash
   tail -f ./logs/audit.log
   
   # 查找错误
   grep ERROR ./logs/audit.log | tail -20
   ```

4. 查看数据库日志
   ```sql
   SELECT * FROM audit_logs 
   WHERE log_level = 'ERROR' 
   ORDER BY created_at DESC 
   LIMIT 10;
   ```

---

### 问题：抓取到代理但验证失败率高（<10% 成功率）

**原因**：
1. 代理质量差
2. 验证太严格
3. 代理源已失效

**解决方案**：
1. 增加超时时间
   ```dotenv
   HTTP_TIMEOUT=15
   CHECK_RETRIES=3
   ```

2. 降低验证线程数（减少并发）
   ```dotenv
   CHECK_WORKERS=10  # 从 30 降低到 10
   ```

3. 尝试其他代理源
   ```bash
   # 查看日志中哪个源最好用
   grep "HTTP_REQUEST" ./logs/audit.log | tail -20
   ```

---

## 🔍 性能问题

### 问题：爬虫运行缓慢

**原因**：
1. 并发设置过低
2. 磁盘 I/O 慢
3. MySQL 连接数限制
4. 网络速度慢

**解决方案**：

**增加并发**：
```dotenv
SOURCE_WORKERS=4        # 增加抓取线程
VALIDATE_WORKERS=50     # 增加验证线程
```

**检查磁盘速度**：
```bash
# Linux
dd if=/dev/zero of=testfile bs=1M count=1024
rm testfile
```

**检查 MySQL 连接**：
```sql
SHOW VARIABLES LIKE 'max_connections';
SHOW STATUS LIKE 'Threads_connected';
```

**检查网络**：
```bash
speedtest --simple
ping -c 10 8.8.8.8
```

---

### 问题：Redis 内存持续增长

**原因**：
1. 代理从未过期
2. 日志未清理
3. 内存泄漏

**解决方案**：
1. 检查 Redis 内存
   ```bash
   redis-cli INFO memory
   redis-cli DBSIZE  # 查看键数量
   ```

2. 清理过期密钥
   ```bash
   redis-cli FLUSHDB  # 清空当前数据库（谨慎）
   ```

3. 优化过期策略
   ```bash
   # 检查过期策略
   redis-cli CONFIG GET maxmemory-policy
   
   # 设置为 LRU 淘汰
   redis-cli CONFIG SET maxmemory-policy allkeys-lru
   ```

---

## 📝 日志问题

### 问题：日志文件不存在或为空

**原因**：
1. 日志功能未启用
2. 日志目录无写入权限
3. 日志级别过高

**解决方案**：
1. 检查环境配置
   ```bash
   grep LOG_ .env
   ```

2. 确保日志目录存在且可写
   ```bash
   mkdir -p logs
   chmod 755 logs
   touch logs/audit.log
   chmod 644 logs/audit.log
   ```

3. 降低日志级别
   ```dotenv
   LOG_LEVEL=DEBUG
   ```

4. 手动测试日志系统
   ```bash
   python -c "
   from crawler.logging import get_logger
   logger = get_logger()
   logger.log_db_operation('INSERT', 'test_table', 1)
   "
   ```

---

### 问题：数据库日志表为空

**原因**：
1. 日志未写入数据库
2. 审计日志功能未集成
3. 配置中禁用了数据库日志

**解决方案**：
1. 检查配置
   ```bash
   grep LOG_DB_WRITE .env
   ```

2. 确保 audit_logs 表存在
   ```sql
   DESCRIBE audit_logs;
   ```

3. 手动测试
   ```bash
   python -c "
   from crawler.config import Settings
   from crawler.logging import get_logger
   
   settings = Settings.from_env()
   logger = get_logger(settings)
   logger.log_db_operation('TEST', 'test', 1)
   
   # 查看日志
   import pymysql
   conn = pymysql.connect(
      host=settings.mysql_host,
      user=settings.mysql_user,
      password=settings.mysql_password,
      database=settings.mysql_database
   )
   with conn.cursor() as c:
      c.execute('SELECT COUNT(*) FROM audit_logs')
      print(c.fetchone())
   conn.close()
   "
   ```

---

## 🆘 高级问题

### 问题：程序随机崩溃

**原因**：
1. 内存不足
2. 连接泄漏
3. 线程池死锁

**解决方案**：
1. 监控系统资源
   ```bash
   # Linux
   top -b -n 1 | head -10
   free -h
   df -h
   ```

2. 降低并发
   ```dotenv
   SOURCE_WORKERS=1
   VALIDATE_WORKERS=10  # 显著降低
   ```

3. 添加错误处理
   ```bash
   python cli.py run 2>&1 | tee crawler.log
   ```

4. 查看详细日志
   ```bash
   LOG_LEVEL=DEBUG python cli.py run
   ```

---

### 问题：定时任务未执行

**原因**（Linux Cron）：
1. Cron 服务未启动
2. 权限问题
3. 路径问题

**解决方案**：
1. 检查 Cron 是否启动
   ```bash
   sudo systemctl status cron
   ```

2. 检查 Crontab
   ```bash
   crontab -l
   ```

3. 测试任务
   ```bash
   # 直接运行以测试
   cd /path/to/ip-pool-crawler && python cli.py run >> /tmp/crawler.log 2>&1
   ```

4. 查看 Cron 日志
   ```bash
   # Linux
   tail -f /var/log/syslog | grep CRON
   # 或
   journalctl --since "1 hour ago" | grep cron
   ```

---

### 问题：Windows 任务计划未执行

**原因**：
1. 任务被禁用
2. 触发条件不满足
3. 脚本权限问题

**解决方案**：
1. 打开任务计划程序
2. 查找你的任务
3. 右键选择"运行"进行手动测试
4. 查看"历史记录"标签查看错误
5. 检查"常规"标签，确保任务已启用

---

## 🤖 通用动态爬虫专项问题

### 问题：启用 `--use-ai` 后没有看到 AI 调用

**现象**：`crawl-custom` 能跑通，但 AI 调用次数为 0。

**排查步骤**：
1. 检查 AI 总开关
   ```dotenv
   USE_AI_FALLBACK=true
   ```
2. 检查触发条件
   ```dotenv
   AI_TRIGGER_ON_LOW_CONFIDENCE=true
   AI_TRIGGER_ON_NO_TABLE=true
   AI_TRIGGER_ON_FAILED_PARSE=true
   ```
3. 检查基础 LLM 配置
   ```dotenv
   LLM_BASE_URL=https://api.openai.com/v1
   LLM_MODEL=gpt-4o-mini
   LLM_API_KEY=your_key
   ```

**验证**：
```bash
python cli.py crawl-custom https://example.com/proxy --use-ai --verbose
```

---

### 问题：分页检测失败，只抓到第一页

**现象**：目标站点有多页，但 `pages_crawled` 始终为 1。

**常见原因**：
1. “下一页”链接文本不标准
2. URL 不含可识别分页参数
3. 站点分页由 JS 动态加载

**解决方案**：
1. 先检查页面是否可提取下一页链接
   ```bash
   python cli.py crawl-custom https://example.com/proxy --max-pages 5 --verbose --no-store
   ```
2. 适当放宽页数上限，确认不是配置提前截止
   ```dotenv
   MAX_PAGES=10
   MAX_PAGES_NO_NEW_IP=5
   ```
3. 若站点为纯 JS 分页，当前版本建议改用其 API 源地址。

---

### 问题：数据精准度低，`invalid` 或待审查数量偏高

**现象**：`valid` 占比低，`review_pending` 高。

**优化建议**：
1. 检查目标页面是否混入非代理文本（广告、注释、脚本）
2. 调高提取质量参数
   ```dotenv
   HEURISTIC_CONFIDENCE_THRESHOLD=0.7
   MIN_EXTRACTION_COUNT=3
   ```
3. 开启 AI 兜底并观察成本
   ```dotenv
   USE_AI_FALLBACK=true
   AI_CACHE_ENABLED=true
   AI_COST_LIMIT_USD=100
   ```

**验证**：
```bash
python cli.py crawl-custom https://example.com/proxy --use-ai --verbose
```

---

## 📞 获取帮助

如问题未解决，请收集以下信息：

1. **环境信息**
   ```bash
   python --version
   mysql --version
   redis-cli --version
   ```

2. **错误信息**
   ```bash
   python cli.py run 2>&1 | head -50
   ```

3. **日志文件**
   ```bash
   cat ./logs/audit.log | tail -50
   ```

4. **数据库状态**
   ```sql
   SELECT * FROM audit_logs WHERE log_level = 'ERROR' ORDER BY created_at DESC LIMIT 10;
   ```

5. **系统资源**
   ```bash
   uname -a
   free -h
   df -h
   ```

---

**相关文档**：
- 👉 [快速开始](./QUICK_START.md)
- 👉 [审计日志](./AUDIT_LOGGING.md)
- 👉 [命令行参考](./CLI_REFERENCE.md)
