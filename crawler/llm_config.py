"""
LLM 配置管理模块

支持多个 LLM 提供商（OpenAI、Azure、Ollama 等）
用户可自主配置 base_url、model、apikey
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    """LLM 配置类"""
    
    base_url: str                    # LLM API 端点
    model: str                       # 模型名称
    api_key: str                     # API 密钥
    timeout_seconds: int = 30        # 请求超时（秒）
    max_retries: int = 3             # 最大重试次数
    enabled: bool = False            # 是否启用 AI 功能
    
    # AI 触发条件
    trigger_on_low_confidence: bool = True
    trigger_on_no_table: bool = True
    trigger_on_failed_parse: bool = True
    trigger_on_user_request: bool = True
    
    # 缓存和成本控制
    cache_enabled: bool = True
    cache_ttl_hours: int = 24
    cost_limit_usd: float = 100.0

    # Prompt 与输入内容策略
    system_prompt: str = "你是资深代理数据抽取器。仅输出合法 JSON，不要输出解释、Markdown 或额外文本。"
    user_prompt_template: str = (
        "任务：从 HTML 中提取代理列表，并严格返回 JSON。\n"
        "规则：\n"
        "1) 仅提取公网 IPv4，过滤私网/保留地址。\n"
        "2) port 必须是 1-65535 的整数。\n"
        "3) protocol 统一为 http/https/socks4/socks5，未知时用 http。\n"
        "4) confidence 取值 0-1。\n"
        "5) 按 ip+port+protocol 去重。\n"
        "6) 若未提取到结果，返回 {\"proxies\":[]}。\n"
        "输出要求：仅输出 JSON 对象，格式为 {\"proxies\":[{\"ip\":\"...\",\"port\":8080,\"protocol\":\"http\",\"confidence\":0.95}]}。\n"
        "上下文：{context_json}\n"
        "HTML：\n{html_snippet}"
    )
    submit_full_html: bool = False
    html_snippet_chars: int = 5000
    
    def __post_init__(self):
        """验证配置"""
        if self.enabled:
            if not self.api_key or self.api_key.strip() == "":
                raise ValueError("启用 AI 时，LLM_API_KEY 不能为空")
            if not self.api_key.replace("dummy", ""):  # 仅 Ollama 允许 dummy key
                if "localhost" not in self.base_url and "127.0.0.1" not in self.base_url:
                    raise ValueError(f"非本地服务需要有效的 API Key: {self.api_key[:10]}...")
        
        if not self.base_url.endswith("/v1") and not self.base_url.endswith("/v1/"):
            # 自动追加 /v1 如果没有
            if not self.base_url.endswith("/"):
                self.base_url += "/v1"
            else:
                self.base_url += "v1"
        
        if self.timeout_seconds < 5:
            raise ValueError("超时时间不能少于 5 秒")
        
        if self.cache_ttl_hours < 1:
            raise ValueError("缓存 TTL 不能少于 1 小时")
        
        if self.cost_limit_usd < 0:
            raise ValueError("成本限制不能为负数")

        if self.html_snippet_chars <= 0:
            raise ValueError("LLM_HTML_SNIPPET_CHARS 必须大于 0")

        if not self.system_prompt or not self.system_prompt.strip():
            raise ValueError("LLM_SYSTEM_PROMPT 不能为空")

        if not self.user_prompt_template or not self.user_prompt_template.strip():
            raise ValueError("LLM_USER_PROMPT_TEMPLATE 不能为空")
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量读取 LLM 配置"""
        
        # 基础配置
        enabled = os.getenv("USE_AI_FALLBACK", "false").lower() == "true"
        base_url = os.getenv(
            "LLM_BASE_URL",
            "https://api.openai.com/v1"
        )
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        api_key = os.getenv("LLM_API_KEY", "")
        timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        
        # AI 触发条件
        trigger_low_confidence = os.getenv(
            "AI_TRIGGER_ON_LOW_CONFIDENCE", "true"
        ).lower() == "true"
        trigger_no_table = os.getenv(
            "AI_TRIGGER_ON_NO_TABLE", "true"
        ).lower() == "true"
        trigger_failed_parse = os.getenv(
            "AI_TRIGGER_ON_FAILED_PARSE", "true"
        ).lower() == "true"
        trigger_user_request = os.getenv(
            "AI_TRIGGER_ON_USER_REQUEST", "true"
        ).lower() == "true"
        
        # 缓存配置
        cache_enabled = os.getenv("AI_CACHE_ENABLED", "true").lower() == "true"
        cache_ttl = int(os.getenv("AI_CACHE_TTL_HOURS", "24"))
        cost_limit = float(os.getenv("AI_COST_LIMIT_USD", "100"))

        # Prompt 与输入内容策略
        system_prompt = os.getenv("LLM_SYSTEM_PROMPT", cls.system_prompt).replace("\\n", "\n")
        user_prompt_template = os.getenv(
            "LLM_USER_PROMPT_TEMPLATE",
            cls.user_prompt_template,
        ).replace("\\n", "\n")
        submit_full_html = os.getenv("LLM_SUBMIT_FULL_HTML", "false").lower() == "true"
        html_snippet_chars = int(os.getenv("LLM_HTML_SNIPPET_CHARS", "5000"))
        
        return cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_seconds=timeout,
            max_retries=max_retries,
            enabled=enabled,
            trigger_on_low_confidence=trigger_low_confidence,
            trigger_on_no_table=trigger_no_table,
            trigger_on_failed_parse=trigger_failed_parse,
            trigger_on_user_request=trigger_user_request,
            cache_enabled=cache_enabled,
            cache_ttl_hours=cache_ttl,
            cost_limit_usd=cost_limit,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            submit_full_html=submit_full_html,
            html_snippet_chars=html_snippet_chars,
        )
    
    @staticmethod
    def validate_api_key(api_key: str, base_url: str) -> bool:
        """验证 API Key 格式"""
        if not api_key:
            return False
        
        base_url_lower = base_url.lower()
        
        # 本地服务可以用 dummy key
        if "localhost" in base_url_lower or "127.0.0.1" in base_url_lower:
            return True
        
        # OpenAI: sk-xxx
        if "openai.com" in base_url_lower:
            # 如果是 Azure，返回 True
            if "azure" in base_url_lower:
                return len(api_key) >= 10  # Azure key 至少 10 个字符
            # 否则检查是否以 sk- 开头（OpenAI）
            return api_key.startswith("sk-")
        
        # Anthropic: sk-ant-xxx
        if "anthropic" in base_url_lower:
            return api_key.startswith("sk-ant-")
        
        # 其他服务：只检查非空
        return len(api_key) > 0
    
    def is_valid(self) -> bool:
        """检查配置是否有效"""
        if not self.enabled:
            return True
        
        # 启用时，必须有有效的配置
        if not self.base_url or not self.model or not self.api_key:
            return False
        
        return self.validate_api_key(self.api_key, self.base_url)
