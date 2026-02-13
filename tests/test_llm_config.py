"""
LLM 配置测试
"""

import pytest
import os
from crawler.llm_config import LLMConfig


class TestLLMConfig:
    """LLM 配置单元测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = LLMConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            api_key="sk-test123"
        )
        assert config.base_url == "https://api.openai.com/v1"
        assert config.model == "gpt-4o-mini"
        assert config.timeout_seconds == 30
        assert config.max_retries == 3
        assert config.enabled == False
        assert config.submit_full_html is False
        assert config.html_snippet_chars == 5000
        assert "仅输出合法 JSON" in config.system_prompt
    
    def test_config_auto_fix_url(self):
        """测试自动修复 URL"""
        config = LLMConfig(
            base_url="https://api.openai.com",
            model="gpt-4o-mini",
            api_key="sk-test123"
        )
        assert config.base_url == "https://api.openai.com/v1"
    
    def test_config_timeout_validation(self):
        """测试超时验证"""
        with pytest.raises(ValueError):
            LLMConfig(
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
                api_key="sk-test123",
                timeout_seconds=3
            )
    
    def test_config_enabled_requires_api_key(self):
        """测试启用后需要 API Key"""
        with pytest.raises(ValueError):
            config = LLMConfig(
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
                api_key="",
                enabled=True
            )
    
    def test_ollama_local_config(self):
        """测试本地 Ollama 配置"""
        config = LLMConfig(
            base_url="http://localhost:11434/v1",
            model="llama2",
            api_key="dummy-key",
            enabled=True
        )
        assert config.enabled == True
        assert config.is_valid() == True
    
    def test_openai_api_key_validation(self):
        """测试 OpenAI API Key 验证"""
        assert LLMConfig.validate_api_key(
            "sk-proj-xyz123",
            "https://api.openai.com/v1"
        ) == True
        
        assert LLMConfig.validate_api_key(
            "invalid-key",
            "https://api.openai.com/v1"
        ) == False
    
    def test_azure_api_key_validation(self):
        """测试 Azure API Key 验证"""
        # Azure 验证相对宽松，只检查长度
        assert LLMConfig.validate_api_key(
            "a" * 20,  # 足够长的 key
            "https://my-resource.openai.azure.com/"
        ) == True
    
    def test_cache_ttl_validation(self):
        """测试缓存 TTL 验证"""
        with pytest.raises(ValueError):
            LLMConfig(
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
                api_key="sk-test123",
                cache_ttl_hours=0
            )
    
    def test_cost_limit_validation(self):
        """测试成本限制验证"""
        with pytest.raises(ValueError):
            LLMConfig(
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
                api_key="sk-test123",
                cost_limit_usd=-10
            )
    
    def test_from_env_disabled_by_default(self):
        """测试默认从 env 读取时禁用 AI"""
        # 确保配置不启用 AI
        os.environ.pop("USE_AI_FALLBACK", None)
        config = LLMConfig.from_env()
        assert config.enabled == False
    
    def test_from_env_default_values(self):
        """测试从 env 读取默认值"""
        os.environ.pop("LLM_BASE_URL", None)
        os.environ.pop("LLM_MODEL", None)
        os.environ.pop("LLM_SYSTEM_PROMPT", None)
        os.environ.pop("LLM_USER_PROMPT_TEMPLATE", None)
        os.environ.pop("LLM_SUBMIT_FULL_HTML", None)
        os.environ.pop("LLM_HTML_SNIPPET_CHARS", None)
        config = LLMConfig.from_env()
        
        assert config.base_url == "https://api.openai.com/v1"
        assert config.model == "gpt-4o-mini"
        assert config.timeout_seconds == 30
        assert config.cache_ttl_hours == 24
        assert config.submit_full_html is False
        assert config.html_snippet_chars == 5000

    def test_from_env_prompt_and_html_strategy(self):
        """测试自定义提示词和 HTML 提交策略"""
        os.environ["LLM_SYSTEM_PROMPT"] = "sys prompt"
        os.environ["LLM_USER_PROMPT_TEMPLATE"] = "ctx={context_json}\\nhtml={html_snippet}"
        os.environ["LLM_SUBMIT_FULL_HTML"] = "true"
        os.environ["LLM_HTML_SNIPPET_CHARS"] = "12000"

        config = LLMConfig.from_env()

        assert config.system_prompt == "sys prompt"
        assert config.user_prompt_template == "ctx={context_json}\nhtml={html_snippet}"
        assert config.submit_full_html is True
        assert config.html_snippet_chars == 12000

        os.environ.pop("LLM_SYSTEM_PROMPT", None)
        os.environ.pop("LLM_USER_PROMPT_TEMPLATE", None)
        os.environ.pop("LLM_SUBMIT_FULL_HTML", None)
        os.environ.pop("LLM_HTML_SNIPPET_CHARS", None)
    
    def test_trigger_conditions(self):
        """测试 AI 触发条件"""
        config = LLMConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            api_key="sk-test123"
        )
        
        assert config.trigger_on_low_confidence == True
        assert config.trigger_on_no_table == True
        assert config.trigger_on_failed_parse == True
        assert config.trigger_on_user_request == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
