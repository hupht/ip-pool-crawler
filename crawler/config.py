import os
from dataclasses import dataclass
from dotenv import load_dotenv

# 自动加载 .env 文件
load_dotenv()


@dataclass
class Settings:
    # 运行参数与连接信息统一配置
    http_timeout: int = 10
    http_retries: int = 1
    user_agent: str = "ip-pool-crawler/0.1"
    source_workers: int = 2
    validate_workers: int = 30
    check_batch_size: int = 1000
    check_workers: int = 20
    check_retries: int = 3
    check_retry_delay: int = 3
    fail_window_hours: int = 24
    fail_threshold: int = 5
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "ip_pool"
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    
    # 日志配置
    log_level: str = "INFO"
    log_file_path: str = "./logs/crawler.log"
    log_file_max_size_mb: int = 100
    log_file_backup_count: int = 10
    log_db_write_enabled: bool = True
    log_db_mask_sensitive: bool = True
    log_file_mask_sensitive: bool = False
    log_db_retention_days: int = 30
    log_archive_path: str = "./logs/archive"

    # 通用动态爬虫配置
    dynamic_crawler_enabled: bool = True
    heuristic_confidence_threshold: float = 0.5
    min_extraction_count: int = 3
    enable_struct_aware_parsing: bool = True
    max_pages: int = 5
    max_pages_no_new_ip: int = 3
    cross_page_dedup: bool = True
    page_fetch_timeout_seconds: int = 10
    use_ai_fallback: bool = False
    error_recovery_mode: str = "retry"
    max_retries_per_page: int = 3
    retry_backoff_seconds: int = 5
    save_failed_pages_snapshot: bool = True
    require_manual_review: bool = False
    save_low_confidence_data: bool = True
    low_confidence_threshold: float = 0.5
    dynamic_crawler_log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        # 从环境变量读取配置，缺失则使用默认值
        timeout = int(os.getenv("HTTP_TIMEOUT", str(cls.http_timeout)))
        retries = int(os.getenv("HTTP_RETRIES", str(cls.http_retries)))
        user_agent = os.getenv("USER_AGENT", cls.user_agent)
        source_workers = int(os.getenv("SOURCE_WORKERS", str(cls.source_workers)))
        validate_workers = int(os.getenv("VALIDATE_WORKERS", str(cls.validate_workers)))
        check_batch_size = int(os.getenv("CHECK_BATCH_SIZE", str(cls.check_batch_size)))
        check_workers = int(os.getenv("CHECK_WORKERS", str(cls.check_workers)))
        check_retries = int(os.getenv("CHECK_RETRIES", str(cls.check_retries)))
        check_retry_delay = int(os.getenv("CHECK_RETRY_DELAY", str(cls.check_retry_delay)))
        fail_window_hours = int(os.getenv("FAIL_WINDOW_HOURS", str(cls.fail_window_hours)))
        fail_threshold = int(os.getenv("FAIL_THRESHOLD", str(cls.fail_threshold)))
        mysql_host = os.getenv("MYSQL_HOST", cls.mysql_host)
        mysql_port = int(os.getenv("MYSQL_PORT", str(cls.mysql_port)))
        mysql_user = os.getenv("MYSQL_USER", cls.mysql_user)
        mysql_password = os.getenv("MYSQL_PASSWORD", cls.mysql_password)
        mysql_database = os.getenv("MYSQL_DATABASE", cls.mysql_database)
        redis_host = os.getenv("REDIS_HOST", cls.redis_host)
        redis_port = int(os.getenv("REDIS_PORT", str(cls.redis_port)))
        redis_db = int(os.getenv("REDIS_DB", str(cls.redis_db)))
        redis_password = os.getenv("REDIS_PASSWORD", cls.redis_password)
        
        # 日志配置加载
        log_level = os.getenv("LOG_LEVEL", cls.log_level)
        log_file_path = os.getenv("LOG_FILE_PATH", cls.log_file_path)
        log_file_max_size_mb = int(os.getenv("LOG_FILE_MAX_SIZE_MB", str(cls.log_file_max_size_mb)))
        log_file_backup_count = int(os.getenv("LOG_FILE_BACKUP_COUNT", str(cls.log_file_backup_count)))
        log_db_write_enabled = os.getenv("LOG_DB_WRITE_ENABLED", "true").lower() == "true"
        log_db_mask_sensitive = os.getenv("LOG_DB_MASK_SENSITIVE", "true").lower() == "true"
        log_file_mask_sensitive = os.getenv("LOG_FILE_MASK_SENSITIVE", "false").lower() == "true"
        log_db_retention_days = int(os.getenv("LOG_DB_RETENTION_DAYS", str(cls.log_db_retention_days)))
        log_archive_path = os.getenv("LOG_ARCHIVE_PATH", cls.log_archive_path)

        # 动态爬虫配置加载
        dynamic_crawler_enabled = os.getenv("DYNAMIC_CRAWLER_ENABLED", "true").lower() == "true"
        heuristic_confidence_threshold = float(
            os.getenv("HEURISTIC_CONFIDENCE_THRESHOLD", str(cls.heuristic_confidence_threshold))
        )
        min_extraction_count = int(os.getenv("MIN_EXTRACTION_COUNT", str(cls.min_extraction_count)))
        enable_struct_aware_parsing = os.getenv(
            "ENABLE_STRUCT_AWARE_PARSING", str(cls.enable_struct_aware_parsing).lower()
        ).lower() == "true"
        max_pages = int(os.getenv("MAX_PAGES", str(cls.max_pages)))
        max_pages_no_new_ip = int(os.getenv("MAX_PAGES_NO_NEW_IP", str(cls.max_pages_no_new_ip)))
        cross_page_dedup = os.getenv("CROSS_PAGE_DEDUP", "true").lower() == "true"
        page_fetch_timeout_seconds = int(
            os.getenv("PAGE_FETCH_TIMEOUT_SECONDS", str(cls.page_fetch_timeout_seconds))
        )
        use_ai_fallback = os.getenv("USE_AI_FALLBACK", "false").lower() == "true"
        error_recovery_mode = os.getenv("ERROR_RECOVERY_MODE", cls.error_recovery_mode)
        max_retries_per_page = int(os.getenv("MAX_RETRIES_PER_PAGE", str(cls.max_retries_per_page)))
        retry_backoff_seconds = int(os.getenv("RETRY_BACKOFF_SECONDS", str(cls.retry_backoff_seconds)))
        save_failed_pages_snapshot = os.getenv(
            "SAVE_FAILED_PAGES_SNAPSHOT", str(cls.save_failed_pages_snapshot).lower()
        ).lower() == "true"
        require_manual_review = os.getenv(
            "REQUIRE_MANUAL_REVIEW", str(cls.require_manual_review).lower()
        ).lower() == "true"
        save_low_confidence_data = os.getenv(
            "SAVE_LOW_CONFIDENCE_DATA", str(cls.save_low_confidence_data).lower()
        ).lower() == "true"
        low_confidence_threshold = float(
            os.getenv("LOW_CONFIDENCE_THRESHOLD", str(cls.low_confidence_threshold))
        )
        dynamic_crawler_log_level = os.getenv("DYNAMIC_CRAWLER_LOG_LEVEL", cls.dynamic_crawler_log_level)
        
        return cls(
            http_timeout=timeout,
            http_retries=retries,
            user_agent=user_agent,
            source_workers=source_workers,
            validate_workers=validate_workers,
            check_batch_size=check_batch_size,
            check_workers=check_workers,
            check_retries=check_retries,
            check_retry_delay=check_retry_delay,
            fail_window_hours=fail_window_hours,
            fail_threshold=fail_threshold,
            mysql_host=mysql_host,
            mysql_port=mysql_port,
            mysql_user=mysql_user,
            mysql_password=mysql_password,
            mysql_database=mysql_database,
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            redis_password=redis_password,
            log_level=log_level,
            log_file_path=log_file_path,
            log_file_max_size_mb=log_file_max_size_mb,
            log_file_backup_count=log_file_backup_count,
            log_db_write_enabled=log_db_write_enabled,
            log_db_mask_sensitive=log_db_mask_sensitive,
            log_file_mask_sensitive=log_file_mask_sensitive,
            log_db_retention_days=log_db_retention_days,
            log_archive_path=log_archive_path,
            dynamic_crawler_enabled=dynamic_crawler_enabled,
            heuristic_confidence_threshold=heuristic_confidence_threshold,
            min_extraction_count=min_extraction_count,
            enable_struct_aware_parsing=enable_struct_aware_parsing,
            max_pages=max_pages,
            max_pages_no_new_ip=max_pages_no_new_ip,
            cross_page_dedup=cross_page_dedup,
            page_fetch_timeout_seconds=page_fetch_timeout_seconds,
            use_ai_fallback=use_ai_fallback,
            error_recovery_mode=error_recovery_mode,
            max_retries_per_page=max_retries_per_page,
            retry_backoff_seconds=retry_backoff_seconds,
            save_failed_pages_snapshot=save_failed_pages_snapshot,
            require_manual_review=require_manual_review,
            save_low_confidence_data=save_low_confidence_data,
            low_confidence_threshold=low_confidence_threshold,
            dynamic_crawler_log_level=dynamic_crawler_log_level,
        )
