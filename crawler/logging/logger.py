"""审计日志记录器 - 支持数据库和文件双写"""

import json
import time
import os
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from crawler.logging.formatters import SensitiveDataMasker, LogFormatter


class AuditLogger:
    """审计日志记录器 - 支持数据库和文件双写"""
    
    LOG_LEVELS = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3}
    
    def __init__(self, settings: Any):
        self.settings = settings
        self.log_dir = Path(settings.log_file_path).parent
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.min_level = self.LOG_LEVELS.get(settings.log_level, 1)
        self.masker = SensitiveDataMasker()
        
    def _should_log(self, level: str) -> bool:
        """判断是否应该记录此级别的日志"""
        return self.LOG_LEVELS.get(level, 1) >= self.min_level
    
    def _write_to_file(self, log_record: Dict[str, Any]) -> None:
        """写入文件日志"""
        try:
            line = LogFormatter.format_for_file(log_record)
            with open(self.settings.log_file_path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception as e:
            print(f"[LOGGING] Failed to write file log: {e}")
    
    def _write_to_db(self, log_record: Dict[str, Any]) -> None:
        """写入数据库日志"""
        # 检查是否启用了数据库日志
        if not self.settings.log_db_write_enabled:
            return
        
        try:
            from crawler.storage import get_mysql_connection
            conn = get_mysql_connection(self.settings)
            
            # 构建 INSERT 语句
            fields = []
            values = []
            placeholders = []
            
            for key, value in log_record.items():
                if value is not None:
                    fields.append(key)
                    values.append(value)
                    placeholders.append('%s')
            
            if not fields:
                return
            
            sql = f"INSERT INTO audit_logs ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            
            with conn.cursor() as cursor:
                cursor.execute(sql, values)
            conn.close()
        except Exception as e:
            print(f"[LOGGING] Failed to write DB log: {e}")
    
    def log_db_operation(
        self,
        operation: str,
        table: str,
        affected_rows: Optional[int] = None,
        sql: Optional[str] = None,
        params: Optional[Dict] = None,
        duration_ms: int = 0,
        before_data: Optional[Dict] = None,
        after_data: Optional[Dict] = None,
        error: Optional[Exception] = None,
        level: str = "INFO",
    ) -> None:
        """记录数据库操作"""
        if not self._should_log(level):
            return
        
        # 对 SQL 参数进行脱敏（分别用于数据库和文件）
        sql_params_db = self.masker.format_for_storage(params, self.settings.log_db_mask_sensitive)
        
        log_record = {
            'log_level': level,
            'operation_type': 'DB_OPERATION',
            'module_name': 'storage',
            'action': f"{operation} on {table}",
            'sql_operation': operation,
            'table_name': table,
            'affected_rows': affected_rows,
            'sql_statement': sql,
            'sql_params': sql_params_db,
            'duration_ms': duration_ms,
            'before_data': self.masker.format_for_storage(before_data, self.settings.log_db_mask_sensitive),
            'after_data': self.masker.format_for_storage(after_data, self.settings.log_db_mask_sensitive),
            'process_id': os.getpid(),
            'created_at': datetime.now(),
        }
        
        if error:
            log_record['log_level'] = 'ERROR'
            log_record['error_code'] = type(error).__name__
            log_record['error_message'] = str(error)[:500]
            log_record['error_stack'] = traceback.format_exc()[:2000]
        
        self._write_to_file(log_record)
        self._write_to_db(log_record)
    
    def log_http_request(
        self,
        url: str,
        status_code: int,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        latency_ms: int = 0,
        error: Optional[Exception] = None,
        level: str = "INFO",
    ) -> None:
        """记录 HTTP 请求"""
        if not self._should_log(level):
            return
        
        # 脱敏 URL（如果包含密码或 token）
        display_url = url
        if self.settings.log_db_mask_sensitive and ('password' in url.lower() or 'token' in url.lower()):
            display_url = url[:50] + "..."
        
        log_record = {
            'log_level': level,
            'operation_type': 'HTTP_REQUEST',
            'module_name': 'fetcher',
            'action': f"Fetch {url[:50]}..." if len(url) > 50 else f"Fetch {url}",
            'request_type': 'HTTP',
            'request_url': display_url,
            'request_status_code': status_code,
            'request_bytes_sent': bytes_sent,
            'request_bytes_received': bytes_received,
            'request_latency_ms': latency_ms,
            'process_id': os.getpid(),
            'created_at': datetime.now(),
        }
        
        if error:
            log_record['log_level'] = 'ERROR'
            log_record['error_code'] = type(error).__name__
            log_record['error_message'] = str(error)[:500]
        
        self._write_to_file(log_record)
        self._write_to_db(log_record)
    
    def log_tcp_check(
        self,
        ip: str,
        port: int,
        success: bool,
        latency_ms: int = 0,
        error: Optional[Exception] = None,
        level: str = "DEBUG",
    ) -> None:
        """记录 TCP 检查"""
        if not self._should_log(level):
            return
        
        # 应用 IP 脱敏
        display_ip = self.masker.mask_ip(ip) if self.settings.log_db_mask_sensitive else ip
        
        log_record = {
            'log_level': level,
            'operation_type': 'TCP_CHECK',
            'module_name': 'validator',
            'action': f"TCP check {display_ip}:{port} - {'OK' if success else 'FAIL'}",
            'request_type': 'TCP',
            'request_status_code': 1 if success else 0,
            'request_latency_ms': latency_ms,
            'process_id': os.getpid(),
            'created_at': datetime.now(),
        }
        
        if error:
            log_record['log_level'] = 'ERROR'
            log_record['error_code'] = type(error).__name__
            log_record['error_message'] = str(error)[:500]
        
        self._write_to_file(log_record)
        self._write_to_db(log_record)
    
    def log_pipeline_event(
        self,
        event_type: str,
        module: str,
        data_count: Optional[int] = None,
        duration_ms: int = 0,
        error: Optional[Exception] = None,
        level: str = "INFO",
    ) -> None:
        """记录流程级事件"""
        if not self._should_log(level):
            return
        
        action = f"Pipeline {event_type}: {module}"
        if data_count is not None:
            action += f" ({data_count} items)"
        if duration_ms:
            action += f" [{duration_ms}ms]"
        
        log_record = {
            'log_level': level,
            'operation_type': f'PIPELINE_{event_type}',
            'module_name': 'pipeline',
            'action': action,
            'duration_ms': duration_ms,
            'process_id': os.getpid(),
            'created_at': datetime.now(),
        }
        
        if error:
            log_record['log_level'] = 'ERROR'
            log_record['error_code'] = type(error).__name__
            log_record['error_message'] = str(error)[:500]
            log_record['error_stack'] = traceback.format_exc()[:2000]
        
        self._write_to_file(log_record)
        self._write_to_db(log_record)


# 全局日志实例
_logger_instance: Optional[AuditLogger] = None


def get_logger(settings: Optional[Any] = None) -> AuditLogger:
    """获取全局日志实例"""
    global _logger_instance
    if _logger_instance is None:
        if settings is None:
            from crawler.runtime import load_settings
            settings = load_settings()
        _logger_instance = AuditLogger(settings)
    return _logger_instance


def reset_logger() -> None:
    """重置日志实例（主要用于测试）"""
    global _logger_instance
    _logger_instance = None
