"""审计日志系统测试"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from crawler.logging.logger import AuditLogger, get_logger, reset_logger
from crawler.logging.formatters import SensitiveDataMasker, LogFormatter


class TestSensitiveDataMasker:
    """敏感信息脱敏测试"""
    
    def test_masker_masks_password(self):
        """验证密码脱敏"""
        data = {"password": "secret123", "username": "admin"}
        masked = SensitiveDataMasker.mask_dict(data, mask=True)
        assert masked["password"] == "***"
        assert masked["username"] == "admin"
    
    def test_masker_masks_api_key(self):
        """验证 API key 脱敏"""
        data = {"api_key": "sk_live_123456", "endpoint": "https://api.example.com"}
        masked = SensitiveDataMasker.mask_dict(data, mask=True)
        assert masked["api_key"] == "***"
        assert masked["endpoint"] == "https://api.example.com"
    
    def test_masker_masks_ip(self):
        """验证 IP 脱敏"""
        data = {"ip": "192.168.1.100", "port": 8080}
        masked = SensitiveDataMasker.mask_dict(data, mask=True)
        assert masked["ip"] == "192.168.1.***"
        assert masked["port"] == 8080
    
    def test_masker_no_mask_when_disabled(self):
        """验证禁用脱敏时不处理"""
        data = {"password": "secret123", "ip": "192.168.1.1"}
        masked = SensitiveDataMasker.mask_dict(data, mask=False)
        assert masked["password"] == "secret123"
        assert masked["ip"] == "192.168.1.1"
    
    def test_masker_recursive_dict(self):
        """验证递归脱敏"""
        data = {
            "user": {
                "name": "john",
                "password": "secret"
            },
            "tokens": ["token1", "token2"]
        }
        masked = SensitiveDataMasker.mask_dict(data, mask=True)
        assert masked["user"]["password"] == "***"
        assert masked["user"]["name"] == "john"
    
    def test_ip_mask_format(self):
        """验证 IP 脱敏格式"""
        assert SensitiveDataMasker.mask_ip("1.2.3.4") == "1.2.3.***"
        assert SensitiveDataMasker.mask_ip("192.168.0.1") == "192.168.0.***"
    
    def test_format_for_storage(self):
        """验证存储格式化"""
        data = {"password": "secret", "ip": "1.2.3.4"}
        result = SensitiveDataMasker.format_for_storage(data, mask=True)
        assert isinstance(result, str)
        assert "***" in result
        assert "secret" not in result


class TestLogFormatter:
    """日志格式化测试"""
    
    def test_format_for_file_basic(self):
        """验证基础日志格式化"""
        log_record = {
            'created_at': '2026-02-12 10:30:00',
            'log_level': 'INFO',
            'module_name': 'storage',
            'action': 'INSERT into proxy_ips',
        }
        formatted = LogFormatter.format_for_file(log_record)
        assert '[2026-02-12 10:30:00]' in formatted
        assert 'INFO' in formatted
        assert 'storage' in formatted
        assert 'INSERT into proxy_ips' in formatted
    
    def test_format_for_file_with_sql_details(self):
        """验证包含 SQL 详情的日志格式"""
        log_record = {
            'created_at': '2026-02-12 10:30:00',
            'log_level': 'INFO',
            'module_name': 'storage',
            'action': 'INSERT on proxy_ips',
            'sql_operation': 'INSERT',
            'table_name': 'proxy_ips',
            'affected_rows': 5,
            'duration_ms': 150,
        }
        formatted = LogFormatter.format_for_file(log_record)
        assert 'SQL: INSERT' in formatted
        assert 'Rows: 5' in formatted
        assert 'Duration: 150ms' in formatted
    
    def test_format_for_file_with_http_details(self):
        """验证包含 HTTP 详情的日志格式"""
        log_record = {
            'created_at': '2026-02-12 10:30:00',
            'log_level': 'INFO',
            'module_name': 'fetcher',
            'action': 'Fetch proxy list',
            'request_type': 'HTTP',
            'request_status_code': 200,
            'request_latency_ms': 500,
        }
        formatted = LogFormatter.format_for_file(log_record)
        assert 'HTTP 200' in formatted
        assert 'Latency: 500ms' in formatted


class TestAuditLogger:
    """审计日志记录器测试"""
    
    @pytest.fixture
    def logger(self):
        """创建测试用的 Logger"""
        settings = MagicMock()
        settings.log_file_path = "/tmp/test_audit.log"
        settings.log_level = "INFO"
        settings.log_db_mask_sensitive = True
        settings.log_file_mask_sensitive = False
        logger = AuditLogger(settings)
        yield logger
    
    def test_logger_respects_log_level(self, logger):
        """验证日志级别过滤"""
        with patch.object(logger, '_write_to_file') as mock_file:
            with patch.object(logger, '_write_to_db') as mock_db:
                # DEBUG 级别在 INFO 以下，应被过滤
                logger.log_db_operation(
                    operation="INSERT",
                    table="proxy_ips",
                    level="DEBUG",
                )
                
                mock_file.assert_not_called()
                mock_db.assert_not_called()
    
    def test_logger_records_db_operation(self, logger):
        """验证数据库操作日志记录"""
        with patch.object(logger, '_write_to_file') as mock_file:
            with patch.object(logger, '_write_to_db') as mock_db:
                logger.log_db_operation(
                    operation="INSERT",
                    table="proxy_ips",
                    affected_rows=10,
                    sql="INSERT INTO proxy_ips ...",
                    params={"ip": "1.2.3.4", "port": 8080},
                    duration_ms=150,
                )
                
                mock_file.assert_called_once()
                mock_db.assert_called_once()
                
                # 验证记录内容
                call_args = mock_db.call_args[0][0]
                assert call_args['operation_type'] == 'DB_OPERATION'
                assert call_args['sql_operation'] == 'INSERT'
                assert call_args['affected_rows'] == 10
    
    def test_logger_masks_sensitive_in_db(self, logger):
        """验证数据库日志脱敏"""
        logger.settings.log_db_mask_sensitive = True
        
        with patch.object(logger, '_write_to_file') as mock_file:
            with patch.object(logger, '_write_to_db') as mock_db:
                logger.log_db_operation(
                    operation="INSERT",
                    table="proxy_ips",
                    params={"ip": "192.168.1.1", "password": "secret"},
                    after_data={"ip": "192.168.1.1", "port": 8080},
                )
                
                db_call = mock_db.call_args[0][0]
                # 验证数据库日志中的 SQL 参数被脱敏
                assert "192.168.1.***" in (db_call.get('sql_params') or "")
    
    def test_logger_records_http_request(self, logger):
        """验证 HTTP 请求日志记录"""
        with patch.object(logger, '_write_to_file') as mock_file:
            with patch.object(logger, '_write_to_db') as mock_db:
                logger.log_http_request(
                    url="https://api.example.com/proxies",
                    status_code=200,
                    bytes_received=5000,
                    latency_ms=350,
                )
                
                mock_file.assert_called_once()
                mock_db.assert_called_once()
                
                call_args = mock_db.call_args[0][0]
                assert call_args['operation_type'] == 'HTTP_REQUEST'
                assert call_args['request_status_code'] == 200
                assert call_args['request_latency_ms'] == 350
    
    def test_logger_records_tcp_check(self, logger):
        """验证 TCP 检查日志记录"""
        with patch.object(logger, '_write_to_file') as mock_file:
            with patch.object(logger, '_write_to_db') as mock_db:
                logger.log_tcp_check(
                    ip="192.168.1.1",
                    port=8080,
                    success=True,
                    latency_ms=50,
                    level="INFO",
                )
                
                mock_file.assert_called_once()
                mock_db.assert_called_once()
                
                call_args = mock_db.call_args[0][0]
                assert call_args['operation_type'] == 'TCP_CHECK'
                assert call_args['request_status_code'] == 1
    
    def test_logger_records_tcp_check_failure(self, logger):
        """验证失败的 TCP 检查日志记录"""
        with patch.object(logger, '_write_to_file') as mock_file:
            with patch.object(logger, '_write_to_db') as mock_db:
                exc = Exception("Connection timeout")
                logger.log_tcp_check(
                    ip="192.168.1.1",
                    port=8080,
                    success=False,
                    error=exc,
                    level="ERROR",
                )
                
                call_args = mock_db.call_args[0][0]
                assert call_args['log_level'] == 'ERROR'
                assert call_args['error_code'] == 'Exception'
                assert 'Connection timeout' in call_args['error_message']
    
    def test_logger_records_pipeline_event(self, logger):
        """验证流程事件日志记录"""
        with patch.object(logger, '_write_to_file') as mock_file:
            with patch.object(logger, '_write_to_db') as mock_db:
                logger.log_pipeline_event(
                    event_type="COMPLETE",
                    module="run_once",
                    data_count=150,
                    duration_ms=5000,
                )
                
                call_args = mock_db.call_args[0][0]
                assert call_args['operation_type'] == 'PIPELINE_COMPLETE'
                assert '150 items' in call_args['action']
                assert '[5000ms]' in call_args['action']


class TestGetLogger:
    """全局日志实例测试"""
    
    def setup_method(self):
        """每个测试前重置全局实例"""
        reset_logger()
    
    def test_get_logger_returns_singleton(self):
        """验证 get_logger 返回单例"""
        reset_logger()
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2
    
    def test_get_logger_with_settings(self):
        """验证 get_logger 接受 settings 参数"""
        reset_logger()
        settings = MagicMock()
        settings.log_file_path = "/tmp/test.log"
        settings.log_level = "DEBUG"
        settings.log_db_mask_sensitive = False
        settings.log_file_mask_sensitive = False
        
        logger = get_logger(settings)
        assert logger.settings is settings
