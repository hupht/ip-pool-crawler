"""日志格式化和敏感信息脱敏"""

import re
import json
from typing import Any, Dict, Optional


class SensitiveDataMasker:
    """敏感信息脱敏工具"""
    
    # 敏感字段列表
    SENSITIVE_KEYS = {
        'password', 'passwd', 'pwd', 'secret', 'token', 'auth',
        'api_key', 'apikey', 'access_token', 'refresh_token',
        'mysql_password', 'redis_password'
    }
    
    @staticmethod
    def is_ip(value: str) -> bool:
        """判断是否为 IP 地址"""
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        return bool(re.match(pattern, str(value)))
    
    @staticmethod
    def mask_ip(ip: str) -> str:
        """脱敏 IP: 1.2.3.4 → 1.2.3.***"""
        try:
            parts = str(ip).split('.')
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.***"
        except Exception:
            pass
        return ip
    
    @classmethod
    def mask_dict(cls, data: Dict[str, Any], mask: bool) -> Dict[str, Any]:
        """递归脱敏字典"""
        if not mask or not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if key_lower in cls.SENSITIVE_KEYS:
                result[key] = "***"
            elif isinstance(value, str) and cls.is_ip(value):
                result[key] = cls.mask_ip(value)
            elif isinstance(value, dict):
                result[key] = cls.mask_dict(value, mask)
            elif isinstance(value, (list, tuple)):
                result[key] = [cls.mask_dict(v, mask) if isinstance(v, dict) else v for v in value]
            else:
                result[key] = value
        return result
    
    @classmethod
    def mask_sql_params(cls, params: Optional[Dict[str, Any]], mask: bool) -> Optional[Dict[str, Any]]:
        """脱敏 SQL 参数"""
        if params is None:
            return None
        return cls.mask_dict(params, mask)
    
    @classmethod
    def format_for_storage(cls, data: Any, mask: bool) -> Optional[str]:
        """格式化数据为 JSON 字符串（用于数据库存储）"""
        if data is None:
            return None
        if isinstance(data, dict):
            data = cls.mask_dict(data, mask)
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            return str(data)


class LogFormatter:
    """日志格式化"""
    
    @staticmethod
    def format_for_file(log_record: Dict[str, Any]) -> str:
        """格式化为文件日志（易读格式）"""
        timestamp = log_record.get('created_at', '')
        level = log_record.get('log_level', 'INFO')
        module = log_record.get('module_name', 'unknown')
        action = log_record.get('action', '')
        
        # 基础行
        line = f"[{timestamp}] {level:8} | {module:30} | {action}"
        
        # 详情行
        details = []
        if log_record.get('sql_operation'):
            details.append(f"SQL: {log_record['sql_operation']} on {log_record.get('table_name', '')}")
            if log_record.get('affected_rows') is not None:
                details.append(f"Rows: {log_record['affected_rows']}")
            if log_record.get('duration_ms'):
                details.append(f"Duration: {log_record['duration_ms']}ms")
        
        if log_record.get('request_type'):
            details.append(f"{log_record['request_type']} {log_record.get('request_status_code', '?')}")
            if log_record.get('request_latency_ms'):
                details.append(f"Latency: {log_record['request_latency_ms']}ms")
        
        if log_record.get('error_message'):
            error_msg = log_record['error_message'][:80]
            details.append(f"ERROR: {error_msg}")
        
        if details:
            line += " | " + " | ".join(details)
        
        return line
