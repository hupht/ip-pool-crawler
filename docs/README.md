# IP Pool Crawler - 文档总览

这是代理 IP 爬虫项目的完整文档。根据你的需要选择相应的文档：

## 🚀 快速开始

**首次使用？** 从这里开始 → [快速开始指南](./QUICK_START.md)

3 步即可运行爬虫，无需手动创建数据库。

## 📖 文档导航

### 必读文档
| 文档 | 适用场景 |
|-----|---------|
| **[快速开始](./QUICK_START.md)** | 首次部署，快速上手 |
| **[部署指南](./DEPLOYMENT.md)** | 生产环境部署，详细检查清单 |
| **[命令行参考](./CLI_REFERENCE.md)** | 学习各个命令的用法 |

### 深度文档
| 文档 | 适用场景 |
|-----|---------|
| **[架构设计](./ARCHITECTURE.md)** | 理解系统各个模块的设计和工作原理 |
| **[审计日志](./AUDIT_LOGGING.md)** | 学习日志系统、查询日志、监控操作 |
| **[故障排查](./TROUBLESHOOTING.md)** | 解决常见问题 |

## ⚡ 核心功能

- 🔄 **多源代理爬取** - 从 5+ 个代理源获取列表
- 🔍 **TCP 验证** - 自动验证代理可用性
- 💾 **双层存储** - MySQL 历史库 + Redis 快速池
- 📊 **审计日志** - 完整的操作日志记录和查询
- ⚙️ **自动初始化** - 首次运行自动建库建表
- 🚀 **并发优化** - 支持高并发抓取和验证

## 📋 最常用的命令

```bash
# 运行完整抓取流程（推荐定时运行）
python cli.py run

# 批量验证代理可用性（定时运行，每 30 分钟）
python cli.py check

# 获取可用代理（应用程序调用）
python cli.py get-proxy --protocol http --country US --count 10

# 诊断数据源
python cli.py diagnose-sources
```

## 🗂️ 项目结构

```
ip-pool-crawler/
├── [`cli.py`](../cli.py)                 # 统一命令行入口
├── [`main.py`](../main.py)               # 简易入口
├── crawler/              # 核心模块
│   ├── [`pipeline.py`](../crawler/pipeline.py)       # 主流程：抓取→解析→入库→验证
│   ├── [`storage.py`](../crawler/storage.py)        # MySQL/Redis 读写
│   ├── [`fetcher.py`](../crawler/fetcher.py)        # HTTP 抓取
│   ├── [`parsers.py`](../crawler/parsers.py)        # 代理列表解析
│   ├── [`validator.py`](../crawler/validator.py)      # TCP 验证和评分
│   ├── [`proxy_picker.py`](../crawler/proxy_picker.py)   # 代理挑选逻辑
│   ├── [`checker.py`](../crawler/checker.py)        # 失败窗口管理
│   ├── [`config.py`](../crawler/config.py)         # 配置管理
│   ├── logging/          # 审计日志模块
│   └── [`sources.py`](../crawler/sources.py)        # 数据源定义
├── tools/                # 工具脚本
├── tests/                # 测试套件
├── sql/
│   └── [`schema.sql`](../sql/schema.sql)        # MySQL 完整结构
├── docs/                 # 文档（本目录）
├── logs/                 # 运行日志（自动创建）
└── .env                  # 环境配置（自己创建）
```

## 🔧 配置要点

### 环境变量（.env 文件）

**必需**：
```dotenv
MYSQL_HOST=127.0.0.1
MYSQL_USER=root
MYSQL_PASSWORD=your_password
REDIS_HOST=127.0.0.1
```

**可选**（有默认值）：
```dotenv
LOG_LEVEL=INFO
LOG_FILE_PATH=./logs/audit.log
LOG_DB_WRITE_ENABLED=true
```

完整列表见 `.env.example`。

## 📊 数据流程

```
[抓取源]
   ↓
[解析代理]
   ↓
[字段规范化]
   ↓
[写入 MySQL]
   ↓
[TCP 验证]
   ↓
[评分和写入 Redis]
```

## 🎯 典型使用场景

### 场景 1: 部署到新服务器
1. 执行 [快速开始](./QUICK_START.md)
2. 配置定时任务（见文档）
3. 完成

### 场景 2: 故障排查
1. 查看 [故障排查](./TROUBLESHOOTING.md)
2. 运行诊断命令
3. 查看日志信息

### 场景 3: 监控系统运行
1. 查看 [审计日志](./AUDIT_LOGGING.md)
2. 使用提供的 SQL 查询
3. 设置监控告警

### 场景 4: 理解系统设计
1. 阅读 [架构设计](./ARCHITECTURE.md)
2. 查看各个模块的源代码
3. 研究数据流和优化点

## 📈 系统要求

| 要求 | 推荐值 | 最低值 |
|------|-------|-------|
| Python | 3.10+ | 3.9+ |
| MySQL | 8.0+ | 5.7+ |
| Redis | 6.0+ | 3.0+ |
| CPU | 2 核+ | 1 核 |
| 内存 | 2GB+ | 512MB |
| 磁盘 | 10GB+ | 1GB |

## 🆘 获取帮助

- 🤔 **常见问题** → [故障排查](./TROUBLESHOOTING.md)
- 📚 **命令使用** → [命令行参考](./CLI_REFERENCE.md)
- 🏗️ **系统设计** → [架构设计](./ARCHITECTURE.md)
- 📊 **日志查询** → [审计日志](./AUDIT_LOGGING.md)

## 📝 最后更新

- **2026-02-12**: 添加审计日志系统，完善文档结构
- **2026-01-15**: 实现自动数据库初始化
- **2025-12-10**: 首次发布

---

**需要帮助？** 查看相应的文档或运行 `python cli.py --help`
