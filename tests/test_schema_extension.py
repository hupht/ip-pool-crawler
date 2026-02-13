"""
SQL Schema 验证测试
验证新增的 4 个表和现有表结构
"""

import pytest


class TestSQLSchema:
    """测试 SQL Schema 的有效性"""
    
    def test_schema_file_exists(self):
        """测试 schema 文件存在"""
        import os
        schema_path = "sql/schema.sql"
        assert os.path.exists(schema_path)
    
    def test_schema_file_readable(self):
        """测试 schema 文件可读"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert len(content) > 0
        assert "CREATE TABLE" in content
    
    def test_schema_contains_crawl_session(self):
        """测试 schema 包含 crawl_session 表"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "CREATE TABLE IF NOT EXISTS crawl_session" in content
        assert "user_url VARCHAR" in content
        assert "page_count INT" in content
    
    def test_schema_contains_crawl_page_log(self):
        """测试 schema 包含 crawl_page_log 表"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "CREATE TABLE IF NOT EXISTS crawl_page_log" in content
        assert "session_id BIGINT UNSIGNED" in content
        assert "page_url VARCHAR" in content
    
    def test_schema_contains_proxy_review_queue(self):
        """测试 schema 包含 proxy_review_queue 表"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "CREATE TABLE IF NOT EXISTS proxy_review_queue" in content
        assert "review_status VARCHAR" in content
        assert "final_status VARCHAR" in content
    
    def test_schema_contains_llm_call_log(self):
        """测试 schema 包含 llm_call_log 表"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "CREATE TABLE IF NOT EXISTS llm_call_log" in content
        assert "llm_provider VARCHAR" in content
        assert "llm_model VARCHAR" in content
    
    def test_schema_foreign_keys(self):
        """测试外键关系"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查外键定义
        assert "FOREIGN KEY (session_id)" in content
        assert "REFERENCES crawl_session (id)" in content
        assert "ON DELETE CASCADE" in content
    
    def test_schema_indexes(self):
        """测试索引定义"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "KEY idx_crawl_session_status" in content
        assert "KEY idx_page_log_session" in content
        assert "KEY idx_queue_status" in content
        assert "KEY idx_llm_session" in content
    
    def test_schema_table_columns_crawl_session(self):
        """测试 crawl_session 表列定义"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 提取 crawl_session 表定义
        start = content.find("CREATE TABLE IF NOT EXISTS crawl_session")
        end = content.find("ENGINE=InnoDB", start)
        table_def = content[start:end]
        
        # 验证重要列
        expected_columns = [
            "id BIGINT UNSIGNED",
            "user_url VARCHAR",
            "page_count INT",
            "ip_count INT",
            "status VARCHAR",
            "started_at DATETIME",
            "completed_at DATETIME"
        ]
        
        for col in expected_columns:
            assert col in table_def
    
    def test_schema_table_columns_crawl_page_log(self):
        """测试 crawl_page_log 表列定义"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        start = content.find("CREATE TABLE IF NOT EXISTS crawl_page_log")
        end = content.find("ENGINE=InnoDB", start)
        table_def = content[start:end]
        
        expected_columns = [
            "session_id BIGINT UNSIGNED",
            "page_url VARCHAR",
            "html_size_bytes INT",
            "detected_ips INT",
            "parse_success TINYINT"
        ]
        
        for col in expected_columns:
            assert col in table_def
    
    def test_schema_table_columns_proxy_review_queue(self):
        """测试 proxy_review_queue 表列定义"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        start = content.find("CREATE TABLE IF NOT EXISTS proxy_review_queue")
        end = content.find("ENGINE=InnoDB", start)
        table_def = content[start:end]
        
        expected_columns = [
            "session_id BIGINT UNSIGNED",
            "ip VARCHAR(45)",
            "port INT",
            "review_status VARCHAR",
            "anomaly_detected TINYINT"
        ]
        
        for col in expected_columns:
            assert col in table_def
    
    def test_schema_table_columns_llm_call_log(self):
        """测试 llm_call_log 表列定义"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        start = content.find("CREATE TABLE IF NOT EXISTS llm_call_log")
        end = content.find("ENGINE=InnoDB", start)
        table_def = content[start:end]
        
        expected_columns = [
            "llm_provider VARCHAR",
            "llm_model VARCHAR",
            "trigger_reason VARCHAR",
            "cost_usd DECIMAL"
        ]
        
        for col in expected_columns:
            assert col in table_def
    
    def test_schema_json_columns(self):
        """测试 JSON 数据类型列"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        # JSON 列应该用于存储复杂数据
        assert "ai_improved_data JSON" in content
        assert "extraction_results JSON" in content
    
    def test_schema_decimal_columns(self):
        """测试 DECIMAL 精度列"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 各种精度的 DECIMAL 列
        assert "DECIMAL(5, 2)" in content  # 毫秒级时间
        assert "DECIMAL(3, 2)" in content  # 置信度 0.00-1.00
        assert "DECIMAL(10, 6)" in content  # 成本 $X.XXXXXX


class TestSchemaExtension:
    """测试 Schema 扩展的逻辑"""
    
    def test_backward_compatibility(self):
        """测试向后兼容性"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 原有表应该仍然存在
        assert "CREATE TABLE IF NOT EXISTS proxy_sources" in content
        assert "CREATE TABLE IF NOT EXISTS proxy_ips" in content
        assert "CREATE TABLE IF NOT EXISTS audit_logs" in content
    
    def test_extension_section_marked(self):
        """测试扩展部分有清晰标记"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "通用动态爬虫支持表" in content
    
    def test_schema_consistency(self):
        """测试 Schema 中字段类型一致"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        # IP 地址应该使用相同的长度定义
        # 检查 proxy_ips 表的 IP 列
        assert "ip VARCHAR(45)" in content
    
    def test_table_dependencies(self):
        """测试表依赖关系正确"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查外键关系
        # crawl_page_log -> crawl_session
        assert content.find("CREATE TABLE IF NOT EXISTS crawl_session") < \
               content.find("CREATE TABLE IF NOT EXISTS crawl_page_log")
        
        # proxy_review_queue 依赖 crawl_session 和 crawl_page_log
        assert content.find("CREATE TABLE IF NOT EXISTS crawl_session") < \
               content.find("CREATE TABLE IF NOT EXISTS proxy_review_queue")
        assert content.find("CREATE TABLE IF NOT EXISTS crawl_page_log") < \
               content.find("CREATE TABLE IF NOT EXISTS proxy_review_queue")


class TestSchemaDocumentation:
    """测试 Schema 文档"""
    
    def test_table_documentation(self):
        """测试表的文档注释"""
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 新表应该有注释
        assert "爬取会话表" in content
        assert "爬取页面日志表" in content
        assert "代理审查队列表" in content
        assert "LLM 调用日志表" in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
