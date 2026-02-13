import pymysql
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from crawler.storage import _load_schema, _init_database_and_schema, _run_with_schema_retry


def test_load_schema_returns_sql_content():
    """验证 schema 加载成功"""
    schema = _load_schema()
    assert "CREATE TABLE IF NOT EXISTS proxy_sources" in schema
    assert "CREATE TABLE IF NOT EXISTS proxy_ips" in schema


def test_init_database_creates_database_and_tables():
    """验证首次初始化时创建数据库和表"""
    settings = MagicMock()
    settings.mysql_host = "localhost"
    settings.mysql_port = 3306
    settings.mysql_user = "root"
    settings.mysql_password = ""
    settings.mysql_database = "test_ip_pool"

    with patch("pymysql.connect") as mock_connect:
        mock_conn1 = MagicMock()
        mock_conn2 = MagicMock()
        mock_connect.side_effect = [mock_conn1, mock_conn2]

        mock_cursor1 = MagicMock()
        mock_cursor2 = MagicMock()
        mock_conn1.cursor.return_value.__enter__.return_value = mock_cursor1
        mock_conn2.cursor.return_value.__enter__.return_value = mock_cursor2

        _init_database_and_schema(settings)

        # 验证两次连接调用
        assert mock_connect.call_count == 2

        # 第一次调用应该创建数据库
        first_call = mock_connect.call_args_list[0]
        assert first_call[1]["host"] == "localhost"
        assert "database" not in first_call[1]  # 第一次不指定数据库

        # 第二次调用应该连接到目标数据库
        second_call = mock_connect.call_args_list[1]
        assert second_call[1]["database"] == "test_ip_pool"

        # 验证 CREATE DATABASE 命令执行
        mock_cursor1.execute.assert_called()
        create_db_call = [c for c in mock_cursor1.execute.call_args_list if "CREATE DATABASE" in str(c)]
        assert len(create_db_call) > 0

        # 验证 CREATE TABLE 命令执行
        mock_cursor2.execute.assert_called()
        create_table_calls = [c for c in mock_cursor2.execute.call_args_list if "CREATE TABLE" in str(c)]
        assert len(create_table_calls) >= 2  # 至少两个表


def test_run_with_schema_retry_retries_on_table_not_found():
    """验证遇到 1146 错误时自动重试和初始化"""
    settings = MagicMock()
    settings.mysql_host = "localhost"
    settings.mysql_port = 3306
    settings.mysql_user = "root"
    settings.mysql_password = ""
    settings.mysql_database = "test_db"

    call_count = [0]

    def runner(cursor):
        call_count[0] += 1
        if call_count[0] == 1:
            raise pymysql.err.ProgrammingError(1146, "Table 'proxy_ips' doesn't exist")
        return "success"

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.ping = MagicMock()

    with patch("crawler.storage._init_database_and_schema") as mock_init:
        result = _run_with_schema_retry(mock_conn, settings, runner)

    assert result == "success"
    mock_init.assert_called_once_with(settings)
    mock_conn.ping.assert_called_once_with(reconnect=True)


def test_run_with_schema_retry_retries_on_database_not_found():
    """验证遇到 1049 错误时自动重试和初始化"""
    settings = MagicMock()
    settings.mysql_host = "localhost"
    settings.mysql_port = 3306
    settings.mysql_user = "root"
    settings.mysql_password = ""
    settings.mysql_database = "test_db"

    call_count = [0]

    def runner(cursor):
        call_count[0] += 1
        if call_count[0] == 1:
            raise pymysql.err.ProgrammingError(1049, "Unknown database 'test_db'")
        return "success"

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.ping = MagicMock()

    with patch("crawler.storage._init_database_and_schema") as mock_init:
        result = _run_with_schema_retry(mock_conn, settings, runner)

    assert result == "success"
    mock_init.assert_called_once_with(settings)


def test_run_with_schema_retry_no_retry_on_other_errors():
    """验证非 1146/1049 错误时不重试"""
    def runner(cursor):
        raise pymysql.err.ProgrammingError(1030, "Got error")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with pytest.raises(pymysql.err.ProgrammingError):
        _run_with_schema_retry(mock_conn, None, runner)


def test_run_with_schema_retry_no_retry_when_settings_none():
    """验证 settings 为 None 时不重试"""
    def runner(cursor):
        raise pymysql.err.ProgrammingError(1146, "Table not found")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with pytest.raises(pymysql.err.ProgrammingError):
        _run_with_schema_retry(mock_conn, None, runner)
