# LLM 集成指南

**版本**：1.0  
**日期**：2026-02-12

---

## 📌 概述

通用动态爬虫支持可选的 AI 辅助功能，可以在启发式检测失败时调用 LLM 来改进精准度。本文档说明如何配置和使用 LLM 功能。

---

## 🤖 LLM 的作用

LLM 在以下场景被调用：

1. **低置信度数据**：启发式检测的置信度 < 阈值
2. **无表格**：页面无表格、列表等结构
3. **解析失败**：完全无法提取任何数据
4. **用户请求**：用户显式要求 AI 检查

LLM 将返回结构化的 JSON 结果，包含：
```json
{
  "proxies": [
    {
      "ip": "1.2.3.4",
      "port": 8080,
      "protocol": "http",
      "confidence": 0.95,
      "reasoning": "从表格的第二列提取"
    }
  ]
}
```

---

## ⚙️ 快速配置

### 1. 启用 LLM 功能

编辑 [`.env`](../.env.example)：

```bash
USE_AI_FALLBACK=true
```

### 2. 配置 LLM 服务

#### 选项 A：使用 OpenAI（推荐新手）

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your-actual-key-here
```

1. 获取 API Key：https://platform.openai.com/api-keys
2. 复制到 `.env` 中
3. 确保账户有足够的配额

#### 选项 B：使用 Azure OpenAI

```bash
LLM_BASE_URL=https://your-resource.openai.azure.com/
LLM_MODEL=your-deployment-name
LLM_API_KEY=your-azure-api-key
```

#### 选项 C：使用本地 Ollama（免费、离线）

先在本地运行 Ollama：
```bash
ollama pull llama2
ollama serve  # 默认监听 http://localhost:11434
```

然后配置：
```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama2
LLM_API_KEY=dummy-key-for-local  # Ollama 不需要真实 key
```

#### 选项 D：使用其他兼容 OpenAI 的服务

任何兼容 OpenAI API 的服务都可以使用。示例：

```bash
# vLLM
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=meta-llama/Llama-2-7b

# LM Studio
LLM_BASE_URL=http://localhost:1234/v1
LLM_MODEL=local-model
```

### 3. 配置触发条件

```bash
# 选择何时调用 AI
AI_TRIGGER_ON_LOW_CONFIDENCE=true    # 低置信度时
AI_TRIGGER_ON_NO_TABLE=true          # 无表格时
AI_TRIGGER_ON_FAILED_PARSE=true      # 解析失败
AI_TRIGGER_ON_USER_REQUEST=true      # 用户请求
```

### 4. 配置成本控制（仅针对付费服务）

```bash
# 缓存设置（降低成本）
AI_CACHE_ENABLED=true
AI_CACHE_TTL_HOURS=24

# 成本限制
AI_COST_LIMIT_USD=100  # 单任务最多 $100
```

### 5. 配置提示词与 HTML 提交策略（新增）

```bash
# 自定义系统提示词
LLM_SYSTEM_PROMPT=你是资深代理数据抽取器。仅输出合法 JSON，不要输出解释、Markdown 或额外文本。

# 自定义用户提示词模板（可用占位符：{context_json}、{html_snippet}、{html}）
LLM_USER_PROMPT_TEMPLATE=任务：从 HTML 中提取代理列表，并严格返回 JSON。\n规则：\n1) 仅提取公网 IPv4，过滤私网/保留地址。\n2) port 必须是 1-65535 的整数。\n3) protocol 统一为 http/https/socks4/socks5，未知时用 http。\n4) confidence 取值 0-1。\n5) 按 ip+port+protocol 去重。\n6) 若未提取到结果，返回 {"proxies":[]}。\n输出要求：仅输出 JSON 对象，格式为 {"proxies":[{"ip":"...","port":8080,"protocol":"http","confidence":0.95}]}。\n上下文：{context_json}\nHTML：\n{html_snippet}

# 是否提交完整 HTML（true=提交全部页面，false=提交片段）
LLM_SUBMIT_FULL_HTML=false

# 仅在 LLM_SUBMIT_FULL_HTML=false 时生效
LLM_HTML_SNIPPET_CHARS=5000
```

⚠️ 说明：提交给 LLM 的字符越少，通常效果越差（上下文不足，漏提取概率更高）。

---

## 💰 成本估算

### OpenAI 成本计算

**gpt-4o-mini** 是目前最便宜的选项：

| 操作 | 耗费 Token | 成本 |
|------|-----------|------|
| 1 个 HTML 页面 | ~12K input | $0.0018 |
| 1 个 LLM 调用 | ~1K output | $0.0006 |
| **单页总成本** | - | **~$0.002** |
| 100 页爬取 | - | **~$0.20** |
| 1000 页爬取 | - | **~$2.00** |

**成本优化**：
1. 减少不必要的 AI 调用（调整触发条件）
2. 启用缓存（相同页面不重复请求）
3. 使用更便宜的模型（gpt-3.5-turbo）
4. 使用本地模型（Ollama 免费）

### 月度预算参考

```
假设每天爬取 1000 个新 URL：

情况 1：完全启用 AI
  - 每日成本：1000 页 × $0.002 = $2
  - 月度成本：$2 × 30 = $60

情况 2：仅在失败时使用 AI（失败率 10%）
  - 每日成本：100 页 × $0.002 = $0.2
  - 月度成本：$0.2 × 30 = $6

情况 3：启用缓存 + 精准触发（有效利用率 5%）
  - 每日成本：50 页 × $0.002 = $0.1
  - 月度成本：$0.1 × 30 = $3
```

---

## 🧪 测试 LLM 配置

### 测试连接

```bash
# 使用 Python 测试
python -c "
from crawler.llm_config import LLMConfig
config = LLMConfig.from_env()
print(f'✓ 配置有效: {config.model} @ {config.base_url}')
"
```

### 测试 API 调用

```bash
python -c "
from crawler.llm_caller import LLMCaller
from crawler.llm_config import LLMConfig

config = LLMConfig.from_env()
caller = LLMCaller(config)

# 简单测试
result = caller.call_llm_for_parsing(
    html='<html><body>1.2.3.4:8080</body></html>',
    context={}
)
print(f'成功: {result}')
"
```

### 查看 LLM 成本日志

```bash
# 查询成本记录
python -c "
from crawler.runtime import load_settings
from crawler.storage import get_mysql_connection

settings = load_settings()
conn = get_mysql_connection(settings)
try:
  with conn.cursor() as cursor:
    cursor.execute('SELECT llm_model, total_tokens, cost_usd, call_status, created_at FROM llm_call_log ORDER BY created_at DESC LIMIT 10')
    for row in cursor.fetchall():
      print(row)
finally:
  conn.close()
"
```

---

## 🔐 安全最佳实践

### 1. 保护 API Key

❌ **不要做**：
```bash
# 不要提交到 Git
git add .env
git commit -m "Add API key"

# 不要放在代码注释中
LLM_API_KEY = "sk-xxx"  # My key
```

✅ **要这样做**：
```bash
# 使用 .gitignore
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Add .env to gitignore"

# 在 .env 中配置
LLM_API_KEY=sk-your-key

# 或使用环境变量
export LLM_API_KEY=sk-your-key
```

### 2. 轮换 API Key

定期更换 API Key（建议每 3 个月）：

```bash
# 1. 从服务商获取新 Key
# 2. 更新 .env
LLM_API_KEY=sk-new-key-here

# 3. 删除旧 Key
# 4. 重启应用
python cli.py crawl-custom https://example.com
```

### 3. 监控成本

定期检查成本日志：

```bash
# 查看今天的 AI 成本
python -c "
from datetime import datetime
from crawler.runtime import load_settings
from crawler.storage import get_mysql_connection

settings = load_settings()
conn = get_mysql_connection(settings)
today = datetime.now().date()

try:
  with conn.cursor() as cursor:
    cursor.execute('''
      SELECT COALESCE(SUM(cost_usd), 0) as total_cost
      FROM llm_call_log
      WHERE DATE(created_at) = %s
    ''', (today,))
    logs = cursor.fetchone()
finally:
  conn.close()

print(f'今日 AI 成本: \${logs[0] or 0:.4f}')
"
```

---

## 🐛 故障排查

### 问题 1：LLM 连接失败

**症状**：`Error connecting to LLM at https://api.openai.com/v1`

**排查步骤**：

```bash
# 1. 检查网络连接
ping api.openai.com

# 2. 检查 API Key
echo $LLM_API_KEY

# 3. 检查 base URL
curl -H "Authorization: Bearer $LLM_API_KEY" \
     https://api.openai.com/v1/models

# 4. 检查 .env 配置
cat .env | grep LLM_
```

### 问题 2：API Rate Limit

**症状**：`Rate limit exceeded. Please retry after 60 seconds`

**解决方案**：
```bash
# 减少并发度
SOURCE_WORKERS=1

# 增加重试延迟
RETRY_BACKOFF_SECONDS=10

# 减少 AI 触发条件
AI_TRIGGER_ON_LOW_CONFIDENCE=false
AI_TRIGGER_ON_NO_TABLE=false
```

### 问题 3：成本增长过快

**症状**：近期 LLM 成本明显上升

**解决方案**：
```bash
# 先减少触发条件
AI_TRIGGER_ON_LOW_CONFIDENCE=false
AI_TRIGGER_ON_NO_TABLE=false

# 或禁用 AI
USE_AI_FALLBACK=false

# 或启用缓存
AI_CACHE_ENABLED=true
```

### 问题 4：JSON 解析错误

**症状**：`Invalid JSON response from LLM`

**可能原因**：
- 模型返回了非 JSON 格式
- 提示词不清楚
- 模型不兼容

**解决方案**：
```bash
# 切换到更可靠的模型
LLM_MODEL=gpt-4o-mini  # 推荐

# 禁用并重新启用 AI
USE_AI_FALLBACK=false
# 重启后
USE_AI_FALLBACK=true
```

---

## 📚 高级用法

### 自定义提示词

推荐直接在 `.env` 配置，无需改源码：

```bash
LLM_SYSTEM_PROMPT=你是资深代理数据抽取器。仅输出合法 JSON，不要输出解释、Markdown 或额外文本。
LLM_USER_PROMPT_TEMPLATE=任务：从 HTML 中提取代理列表，并严格返回 JSON。\n规则：\n1) 仅提取公网 IPv4，过滤私网/保留地址。\n2) port 必须是 1-65535 的整数。\n3) protocol 统一为 http/https/socks4/socks5，未知时用 http。\n4) confidence 取值 0-1。\n5) 按 ip+port+protocol 去重。\n6) 若未提取到结果，返回 {"proxies":[]}。\n输出要求：仅输出 JSON 对象，格式为 {"proxies":[{"ip":"...","port":8080,"protocol":"http","confidence":0.95}]}。\n上下文：{context_json}\nHTML：\n{html_snippet}

# 提交策略
LLM_SUBMIT_FULL_HTML=false
LLM_HTML_SNIPPET_CHARS=5000
```

⚠️ 提示：当 `LLM_SUBMIT_FULL_HTML=false` 时，提交字符越少，提取效果通常越差。

### 使用自定义模型

```bash
# 使用 Anthropic Claude
LLM_BASE_URL=https://api.anthropic.com/v1
LLM_MODEL=claude-3-haiku
LLM_API_KEY=sk-ant-xxx

# 使用 Google Gemini
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
LLM_MODEL=gemini-pro
LLM_API_KEY=your-gemini-key
```

### 批量成本估算

```python
from crawler.llm_caller import estimate_batch_cost

# 估算爬取 100 个 URL 的成本
# 假设 10% 调用 AI
total_cost = estimate_batch_cost(
    urls_count=100,
    ai_call_rate=0.1,
    model='gpt-4o-mini'
)
print(f"预计成本: ${total_cost:.2f}")
```

---

## 📞 支持

- **问题**：见本文档下方的故障排查
- **更多配置**：见 [配置指南](./UNIVERSAL_CRAWLER_CONFIG.md)
- **使用示例**：见 [使用指南](./UNIVERSAL_CRAWLER_USAGE.md)
