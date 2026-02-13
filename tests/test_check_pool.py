from tools import check_pool


def test_check_proxy_retries_until_success(monkeypatch):
    calls = []

    def fake_tcp_check(host, port, timeout):
        calls.append((host, port, timeout))
        return (len(calls) >= 2, 123 if len(calls) >= 2 else 0)

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(check_pool, "tcp_check", fake_tcp_check)
    monkeypatch.setattr(check_pool.time, "sleep", fake_sleep)

    success, latency = check_pool.check_proxy("1.2.3.4", 8080, timeout=2, retries=3, retry_delay=3)

    assert success is True
    assert latency == 123
    assert len(sleep_calls) == 1


def test_check_proxy_retries_all_fail(monkeypatch):
    def fake_tcp_check(_host, _port, timeout=None):
        return False, 0

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(check_pool, "tcp_check", fake_tcp_check)
    monkeypatch.setattr(check_pool.time, "sleep", fake_sleep)

    success, latency = check_pool.check_proxy("1.2.3.4", 8080, timeout=2, retries=3, retry_delay=3)

    assert success is False
    assert latency == 0
    assert sleep_calls == [3, 3]


def test_run_check_batch_supports_tuple_records(monkeypatch):
    class _Settings:
        check_batch_size = 10
        check_workers = 1
        http_timeout = 1
        check_retries = 1
        check_retry_delay = 0
        fail_window_hours = 24
        fail_threshold = 5

    calls = {"update": 0}

    monkeypatch.setattr(check_pool, "set_settings_for_retry", lambda settings: None)
    monkeypatch.setattr(
        check_pool,
        "get_mysql_connection",
        lambda settings: type("_Conn", (), {"close": lambda self: None})(),
    )
    monkeypatch.setattr(
        check_pool,
        "fetch_check_batch",
        lambda conn, batch_size: [(1, "1.2.3.4", 8080, "http", None, 0)],
    )
    monkeypatch.setattr(check_pool, "check_proxy", lambda ip, port, timeout, retries, retry_delay: (True, 120))
    monkeypatch.setattr(
        check_pool,
        "apply_fail_window",
        lambda **kwargs: type("_Result", (), {"fail_window_start": None, "fail_count": 0, "is_deleted": False})(),
    )
    monkeypatch.setattr(
        check_pool,
        "update_proxy_check_with_window",
        lambda conn, proxy_id, *args, **kwargs: calls.__setitem__("update", calls["update"] + (1 if proxy_id == 1 else 0)),
    )

    check_pool.run_check_batch(_Settings())
    assert calls["update"] == 1
