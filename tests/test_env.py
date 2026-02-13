from crawler.config import Settings


def test_settings_loads_defaults():
    settings = Settings.from_env()
    assert settings.http_timeout > 0
    assert settings.source_workers > 0
    assert settings.validate_workers > 0
    assert settings.check_batch_size > 0
    assert settings.check_workers > 0
    assert settings.check_retries > 0
    assert settings.check_retry_delay > 0
    assert settings.fail_window_hours > 0
    assert settings.fail_threshold > 0
    assert settings.dynamic_crawler_enabled is True
    assert settings.max_pages > 0
    assert settings.max_pages_no_new_ip > 0
    assert settings.page_fetch_timeout_seconds > 0


def test_settings_loads_dynamic_env_overrides(monkeypatch):
    monkeypatch.setenv("HEURISTIC_CONFIDENCE_THRESHOLD", "0.75")
    monkeypatch.setenv("MIN_EXTRACTION_COUNT", "6")
    monkeypatch.setenv("ENABLE_STRUCT_AWARE_PARSING", "false")
    monkeypatch.setenv("ERROR_RECOVERY_MODE", "skip")
    monkeypatch.setenv("MAX_RETRIES_PER_PAGE", "7")
    monkeypatch.setenv("RETRY_BACKOFF_SECONDS", "9")
    monkeypatch.setenv("SAVE_FAILED_PAGES_SNAPSHOT", "false")
    monkeypatch.setenv("REQUIRE_MANUAL_REVIEW", "true")
    monkeypatch.setenv("SAVE_LOW_CONFIDENCE_DATA", "false")
    monkeypatch.setenv("LOW_CONFIDENCE_THRESHOLD", "0.35")
    monkeypatch.setenv("DYNAMIC_CRAWLER_LOG_LEVEL", "DEBUG")

    settings = Settings.from_env()

    assert settings.heuristic_confidence_threshold == 0.75
    assert settings.min_extraction_count == 6
    assert settings.enable_struct_aware_parsing is False
    assert settings.error_recovery_mode == "skip"
    assert settings.max_retries_per_page == 7
    assert settings.retry_backoff_seconds == 9
    assert settings.save_failed_pages_snapshot is False
    assert settings.require_manual_review is True
    assert settings.save_low_confidence_data is False
    assert settings.low_confidence_threshold == 0.35
    assert settings.dynamic_crawler_log_level == "DEBUG"
