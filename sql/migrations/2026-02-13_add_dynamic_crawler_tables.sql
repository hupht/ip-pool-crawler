-- Migration: add dynamic crawler support tables
-- Date: 2026-02-13
-- Note: idempotent migration, safe to run multiple times

CREATE TABLE IF NOT EXISTS crawl_session (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_url VARCHAR(512) NOT NULL,
  page_count INT NOT NULL DEFAULT 1,
  ip_count INT NOT NULL DEFAULT 0,
  proxy_count INT NOT NULL DEFAULT 0,
  max_pages INT NOT NULL DEFAULT 5,
  max_pages_no_new_ip INT NOT NULL DEFAULT 2,
  page_fetch_timeout_seconds INT NOT NULL DEFAULT 30,
  cross_page_dedup TINYINT(1) NOT NULL DEFAULT 1,
  use_ai_fallback TINYINT(1) NOT NULL DEFAULT 0,
  ai_trigger_on_low_confidence TINYINT(1) NOT NULL DEFAULT 1,
  ai_trigger_on_no_table TINYINT(1) NOT NULL DEFAULT 1,
  ai_trigger_on_failed_parse TINYINT(1) NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  error_message LONGTEXT NULL,
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  duration_seconds INT NULL,
  PRIMARY KEY (id),
  KEY idx_crawl_session_status (status),
  KEY idx_crawl_session_created (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS crawl_page_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id BIGINT UNSIGNED NOT NULL,
  page_url VARCHAR(512) NOT NULL,
  page_number INT NOT NULL,
  html_size_bytes INT NOT NULL DEFAULT 0,
  table_count INT NOT NULL DEFAULT 0,
  list_count INT NOT NULL DEFAULT 0,
  json_block_count INT NOT NULL DEFAULT 0,
  text_block_count INT NOT NULL DEFAULT 0,
  detected_ips INT NOT NULL DEFAULT 0,
  detected_ip_port_pairs INT NOT NULL DEFAULT 0,
  extracted_proxies INT NOT NULL DEFAULT 0,
  http_status_code INT NULL,
  fetch_time_seconds DECIMAL(5, 2) NULL,
  parser_type VARCHAR(32) NULL,
  structure_confidence DECIMAL(3, 2) NOT NULL DEFAULT 0.0,
  extraction_confidence DECIMAL(3, 2) NOT NULL DEFAULT 0.0,
  parse_success TINYINT(1) NOT NULL DEFAULT 1,
  error_message LONGTEXT NULL,
  has_next_page TINYINT(1) NOT NULL DEFAULT 0,
  next_page_url VARCHAR(512) NULL,
  pagination_confidence DECIMAL(3, 2) NOT NULL DEFAULT 0.0,
  crawled_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_page_log_session (session_id),
  KEY idx_page_log_crawled (crawled_at),
  CONSTRAINT fk_page_log_session
    FOREIGN KEY (session_id)
    REFERENCES crawl_session (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS proxy_review_queue (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id BIGINT UNSIGNED NOT NULL,
  page_log_id BIGINT UNSIGNED NOT NULL,
  ip VARCHAR(45) NOT NULL,
  port INT NOT NULL,
  protocol VARCHAR(16) NULL,
  detected_via VARCHAR(32) NOT NULL,
  heuristic_confidence DECIMAL(3, 2) NOT NULL DEFAULT 0.0,
  validation_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  anomaly_detected TINYINT(1) NOT NULL DEFAULT 0,
  anomaly_reason VARCHAR(255) NULL,
  ai_improvement_needed TINYINT(1) NOT NULL DEFAULT 0,
  ai_improvement_reason VARCHAR(255) NULL,
  ai_improved_data JSON NULL,
  review_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  reviewer_notes LONGTEXT NULL,
  final_status VARCHAR(32) NULL,
  added_to_pool TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at DATETIME NULL,
  PRIMARY KEY (id),
  KEY idx_queue_session (session_id),
  KEY idx_queue_status (review_status),
  KEY idx_queue_created (created_at),
  CONSTRAINT fk_queue_session
    FOREIGN KEY (session_id)
    REFERENCES crawl_session (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_queue_page_log
    FOREIGN KEY (page_log_id)
    REFERENCES crawl_page_log (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS llm_call_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id BIGINT UNSIGNED NOT NULL,
  page_log_id BIGINT UNSIGNED NULL,
  llm_provider VARCHAR(32) NOT NULL,
  llm_model VARCHAR(64) NOT NULL,
  llm_base_url VARCHAR(256) NOT NULL,
  trigger_reason VARCHAR(64) NOT NULL,
  input_context LONGTEXT NOT NULL,
  input_tokens INT NOT NULL DEFAULT 0,
  response_text LONGTEXT NULL,
  output_tokens INT NOT NULL DEFAULT 0,
  total_tokens INT NOT NULL DEFAULT 0,
  extraction_results JSON NULL,
  extracted_proxy_count INT NOT NULL DEFAULT 0,
  cost_usd DECIMAL(10, 6) NOT NULL DEFAULT 0.0,
  call_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  error_message LONGTEXT NULL,
  retry_count INT NOT NULL DEFAULT 0,
  cache_hit TINYINT(1) NOT NULL DEFAULT 0,
  cache_key VARCHAR(512) NULL,
  call_time_seconds DECIMAL(5, 2) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_llm_session (session_id),
  KEY idx_llm_status (call_status),
  KEY idx_llm_created (created_at),
  KEY idx_llm_cache_key (cache_key),
  CONSTRAINT fk_llm_session
    FOREIGN KEY (session_id)
    REFERENCES crawl_session (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_llm_page_log
    FOREIGN KEY (page_log_id)
    REFERENCES crawl_page_log (id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
