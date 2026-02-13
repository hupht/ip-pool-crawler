-- IP pool schema
-- Run this in your MySQL database (create database separately if needed)

CREATE TABLE IF NOT EXISTS proxy_sources (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(64) NOT NULL,
  url VARCHAR(255) NOT NULL,
  parser_key VARCHAR(64) NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  last_fetch_at DATETIME NULL,
  fail_count INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_proxy_sources_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS proxy_ips (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ip VARCHAR(45) NOT NULL,
  port INT NOT NULL,
  protocol VARCHAR(16) NOT NULL,
  anonymity VARCHAR(32) NULL,
  country VARCHAR(64) NULL,
  region VARCHAR(64) NULL,
  isp VARCHAR(64) NULL,
  source_id BIGINT UNSIGNED NULL,
  first_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_checked_at DATETIME NULL,
  latency_ms INT NULL,
  is_alive TINYINT(1) NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  fail_window_start DATETIME NULL,
  fail_count INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_proxy_ips (ip, port, protocol),
  KEY idx_proxy_ips_alive_checked (is_alive, last_checked_at),
  CONSTRAINT fk_proxy_ips_source
    FOREIGN KEY (source_id)
    REFERENCES proxy_sources (id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  log_level VARCHAR(16) NOT NULL DEFAULT 'INFO',
  operation_type VARCHAR(32) NOT NULL,
  module_name VARCHAR(64) NOT NULL,
  action VARCHAR(255) NOT NULL,
  
  -- 数据库操作字段
  sql_operation VARCHAR(32) NULL,
  table_name VARCHAR(64) NULL,
  affected_rows INT NULL,
  sql_statement LONGTEXT NULL,
  sql_params JSON NULL,
  duration_ms INT NULL,
  
  -- HTTP/TCP 请求字段
  request_type VARCHAR(16) NULL,
  request_url VARCHAR(512) NULL,
  request_status_code INT NULL,
  request_bytes_sent INT NULL,
  request_bytes_received INT NULL,
  request_latency_ms INT NULL,
  
  -- 数据快照字段
  before_data JSON NULL,
  after_data JSON NULL,
  
  -- 错误字段
  error_code VARCHAR(32) NULL,
  error_message LONGTEXT NULL,
  error_stack LONGTEXT NULL,
  
  -- 执行环境字段
  process_id INT NULL,
  thread_id INT NULL,
  source_module VARCHAR(64) NULL,
  
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_logs_created (created_at),
  KEY idx_logs_operation (operation_type),
  KEY idx_logs_level (log_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 自动清理事件（30天）
CREATE EVENT IF NOT EXISTS cleanup_audit_logs
ON SCHEDULE EVERY 1 DAY
STARTS CURRENT_TIMESTAMP
DO
  DELETE FROM audit_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);

-- ===============================================
-- 通用动态爬虫支持表
-- ===============================================

-- 爬取会话表 - 记录每次爬取任务的元数据
CREATE TABLE IF NOT EXISTS crawl_session (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_url VARCHAR(512) NOT NULL,
  page_count INT NOT NULL DEFAULT 1,
  ip_count INT NOT NULL DEFAULT 0,
  proxy_count INT NOT NULL DEFAULT 0,
  
  -- 爬取配置
  max_pages INT NOT NULL DEFAULT 5,
  max_pages_no_new_ip INT NOT NULL DEFAULT 2,
  page_fetch_timeout_seconds INT NOT NULL DEFAULT 30,
  cross_page_dedup TINYINT(1) NOT NULL DEFAULT 1,
  
  -- LLM 相关
  use_ai_fallback TINYINT(1) NOT NULL DEFAULT 0,
  ai_trigger_on_low_confidence TINYINT(1) NOT NULL DEFAULT 1,
  ai_trigger_on_no_table TINYINT(1) NOT NULL DEFAULT 1,
  ai_trigger_on_failed_parse TINYINT(1) NOT NULL DEFAULT 1,
  
  -- 状态
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  error_message LONGTEXT NULL,
  
  -- 时间戳
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  duration_seconds INT NULL,
  
  PRIMARY KEY (id),
  KEY idx_crawl_session_status (status),
  KEY idx_crawl_session_created (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 爬取页面日志表 - 记录每个爬取页面的详细信息
CREATE TABLE IF NOT EXISTS crawl_page_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id BIGINT UNSIGNED NOT NULL,
  page_url VARCHAR(512) NOT NULL,
  page_number INT NOT NULL,
  
  -- 内容统计
  html_size_bytes INT NOT NULL DEFAULT 0,
  table_count INT NOT NULL DEFAULT 0,
  list_count INT NOT NULL DEFAULT 0,
  json_block_count INT NOT NULL DEFAULT 0,
  text_block_count INT NOT NULL DEFAULT 0,
  
  -- 检测结果
  detected_ips INT NOT NULL DEFAULT 0,
  detected_ip_port_pairs INT NOT NULL DEFAULT 0,
  extracted_proxies INT NOT NULL DEFAULT 0,
  
  -- HTTP 交互
  http_status_code INT NULL,
  fetch_time_seconds DECIMAL(5, 2) NULL,
  parser_type VARCHAR(32) NULL,
  
  -- 分析置信度
  structure_confidence DECIMAL(3, 2) NOT NULL DEFAULT 0.0,
  extraction_confidence DECIMAL(3, 2) NOT NULL DEFAULT 0.0,
  
  -- 状态
  parse_success TINYINT(1) NOT NULL DEFAULT 1,
  error_message LONGTEXT NULL,
  
  -- 分页检测
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

-- 代理审查队列表 - 待审查/需要改进的代理列表
CREATE TABLE IF NOT EXISTS proxy_review_queue (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id BIGINT UNSIGNED NOT NULL,
  page_log_id BIGINT UNSIGNED NOT NULL,
  
  ip VARCHAR(45) NOT NULL,
  port INT NOT NULL,
  protocol VARCHAR(16) NULL,
  detected_via VARCHAR(32) NOT NULL,
  
  -- 可信度指标
  heuristic_confidence DECIMAL(3, 2) NOT NULL DEFAULT 0.0,
  validation_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  anomaly_detected TINYINT(1) NOT NULL DEFAULT 0,
  anomaly_reason VARCHAR(255) NULL,
  
  -- AI 改进
  ai_improvement_needed TINYINT(1) NOT NULL DEFAULT 0,
  ai_improvement_reason VARCHAR(255) NULL,
  ai_improved_data JSON NULL,
  
  -- 审查状态
  review_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  reviewer_notes LONGTEXT NULL,
  
  -- 最终结果
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

-- LLM 调用日志表 - 记录所有 LLM API 调用
CREATE TABLE IF NOT EXISTS llm_call_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id BIGINT UNSIGNED NOT NULL,
  page_log_id BIGINT UNSIGNED NULL,
  
  -- LLM 配置
  llm_provider VARCHAR(32) NOT NULL,
  llm_model VARCHAR(64) NOT NULL,
  llm_base_url VARCHAR(256) NOT NULL,
  
  -- 请求信息
  trigger_reason VARCHAR(64) NOT NULL,
  input_context LONGTEXT NOT NULL,
  input_tokens INT NOT NULL DEFAULT 0,
  
  -- 响应信息
  response_text LONGTEXT NULL,
  output_tokens INT NOT NULL DEFAULT 0,
  total_tokens INT NOT NULL DEFAULT 0,
  
  -- 解析结果
  extraction_results JSON NULL,
  extracted_proxy_count INT NOT NULL DEFAULT 0,
  
  -- 成本计算
  cost_usd DECIMAL(10, 6) NOT NULL DEFAULT 0.0,
  
  -- 状态
  call_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  error_message LONGTEXT NULL,
  retry_count INT NOT NULL DEFAULT 0,
  
  -- 缓存
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